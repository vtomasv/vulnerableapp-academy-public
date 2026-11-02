#!/usr/bin/env python3
"""Small, local-only OpenAI chat-completions adapter for Ollama.

This process intentionally has a narrow protocol surface:
* it listens only on 127.0.0.1:11435;
* it talks only to the fixed Ollama service URLs below; and
* it exposes only /health, /v1/models, and /v1/chat/completions.

The adapter always asks Ollama for NDJSON streaming.  It can then expose the
same response as either OpenAI SSE or one accumulated chat.completion object.
"""

from __future__ import annotations

import copy
import json
import math
import os
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener


HOST = "127.0.0.1"
PORT = 11435
UPSTREAM_CHAT_URL = "http://ollama:11434/api/chat"
UPSTREAM_TAGS_URL = "http://ollama:11434/api/tags"
DEFAULT_MODEL = "huihui_ai/Qwen3.8-abliterated:27b"
UPSTREAM_TIMEOUT_SECONDS = min(max(int(os.environ.get("HARNESS_UPSTREAM_TIMEOUT", "1800")), 30), 3600)
OLLAMA_NUM_THREADS = min(max(int(os.environ.get("OLLAMA_NUM_THREADS", "12")), 1), 64)
OLLAMA_NUM_CTX = min(max(int(os.environ.get("OLLAMA_CONTEXT_LENGTH", "16384")), 2048), 32768)
MAX_REQUEST_BODY_BYTES = 512 * 1024


class RequestValidationError(Exception):
    """A safe, client-facing 400 error without implementation details."""

    def __init__(self, message: str, param: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.param = param


class UpstreamError(Exception):
    """An upstream failure that is safe to expose as a generic 502."""

    pass


class ClientDisconnected(Exception):
    """The peer closed a response while it was being written."""

    pass


def configured_model() -> str:
    """Return the one model this adapter is willing to serve."""

    value = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
    value = value.strip()
    return value or DEFAULT_MODEL


def _is_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _require_string(value: Any, param: str) -> str:
    if not isinstance(value, str):
        raise RequestValidationError(f"{param} must be a string", param)
    return value


def _json_arguments(value: Any, param: str) -> Any:
    """Convert OpenAI's JSON-string arguments to Ollama's JSON object."""

    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            raise RequestValidationError(f"{param} must contain valid JSON", param)
        if not isinstance(decoded, dict):
            raise RequestValidationError(f"{param} must decode to a JSON object", param)
        return decoded
    if isinstance(value, dict):
        return copy.deepcopy(value)
    raise RequestValidationError(f"{param} must decode to a JSON object", param)


def convert_messages(messages: Any) -> List[Dict[str, Any]]:
    """Translate OpenAI messages to Ollama chat messages.

    Ollama expects tool-call arguments as decoded JSON.  Ollama tool result
    messages identify the function with ``tool_name`` rather than the OpenAI
    ``tool_call_id``; the latter is resolved from preceding assistant calls.
    """

    if not isinstance(messages, list):
        raise RequestValidationError("messages must be an array", "messages")
    if not messages:
        raise RequestValidationError("messages must not be empty", "messages")

    tool_names: Dict[str, str] = {}
    converted: List[Dict[str, Any]] = []

    for message_index, message in enumerate(messages):
        param = f"messages[{message_index}]"
        if not isinstance(message, dict):
            raise RequestValidationError(f"{param} must be an object", param)

        role = _require_string(message.get("role"), f"{param}.role")
        if role not in {"system", "user", "assistant", "tool"}:
            raise RequestValidationError(f"unsupported message role: {role}", f"{param}.role")

        if role == "tool":
            content = message.get("content")
            if not isinstance(content, str):
                raise RequestValidationError(f"{param}.content must be a string", f"{param}.content")
            call_id = _require_string(message.get("tool_call_id"), f"{param}.tool_call_id")
            tool_name = tool_names.get(call_id)
            if not tool_name:
                raise RequestValidationError(
                    f"unknown tool_call_id: {call_id}", f"{param}.tool_call_id"
                )
            converted.append({"role": "tool", "content": content, "tool_name": tool_name})
            continue

        content = message.get("content", "")
        if content is None and role == "assistant":
            content = ""
        if not isinstance(content, str):
            raise RequestValidationError(f"{param}.content must be a string", f"{param}.content")

        output: Dict[str, Any] = {"role": role, "content": content}

        if role == "assistant" and "tool_calls" in message:
            calls = message.get("tool_calls")
            if not isinstance(calls, list):
                raise RequestValidationError(f"{param}.tool_calls must be an array", f"{param}.tool_calls")

            native_calls: List[Dict[str, Any]] = []
            for call_index, call in enumerate(calls):
                call_param = f"{param}.tool_calls[{call_index}]"
                if not isinstance(call, dict):
                    raise RequestValidationError(f"{call_param} must be an object", call_param)

                call_id = _require_string(call.get("id"), f"{call_param}.id")
                function = call.get("function")
                if not isinstance(function, dict):
                    raise RequestValidationError(f"{call_param}.function must be an object", f"{call_param}.function")
                name = _require_string(function.get("name"), f"{call_param}.function.name")
                if not name:
                    raise RequestValidationError(
                        f"{call_param}.function.name must not be empty", f"{call_param}.function.name"
                    )
                if "arguments" not in function:
                    raise RequestValidationError(
                        f"{call_param}.function.arguments is required", f"{call_param}.function.arguments"
                    )

                native_call = copy.deepcopy(call)
                native_function = copy.deepcopy(function)
                native_function["arguments"] = _json_arguments(
                    function["arguments"], f"{call_param}.function.arguments"
                )
                native_call["function"] = native_function
                native_calls.append(native_call)
                tool_names[call_id] = name

            output["tool_calls"] = native_calls

        converted.append(output)

    return converted


def _validate_tools(tools: Any) -> List[Dict[str, Any]]:
    if not isinstance(tools, list):
        raise RequestValidationError("tools must be an array", "tools")

    result: List[Dict[str, Any]] = []
    for index, tool in enumerate(tools):
        param = f"tools[{index}]"
        if not isinstance(tool, dict):
            raise RequestValidationError(f"{param} must be an object", param)
        if tool.get("type") != "function":
            raise RequestValidationError(f"{param}.type must be function", f"{param}.type")
        function = tool.get("function")
        if not isinstance(function, dict):
            raise RequestValidationError(f"{param}.function must be an object", f"{param}.function")
        name = function.get("name")
        if not isinstance(name, str) or not name:
            raise RequestValidationError(f"{param}.function.name must be a non-empty string", f"{param}.function.name")
        if "description" in function and not isinstance(function["description"], str):
            raise RequestValidationError(
                f"{param}.function.description must be a string", f"{param}.function.description"
            )
        if "parameters" in function and not isinstance(function["parameters"], dict):
            raise RequestValidationError(
                f"{param}.function.parameters must be an object", f"{param}.function.parameters"
            )
        # Descriptors are intentionally passed through unchanged after the
        # shape checks above; Ollama accepts the OpenAI function descriptor.
        result.append(copy.deepcopy(tool))
    return result


def _positive_integer(value: Any, param: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RequestValidationError(f"{param} must be an integer", param)
    if value < 0:
        raise RequestValidationError(f"{param} must not be negative", param)
    return value


def _request_num_predict(request: Mapping[str, Any]) -> int:
    for key in ("max_tokens", "max_completion_tokens"):
        if key in request:
            _positive_integer(request[key], key)

    # Match the requested ``request.max_tokens || request.max_completion_tokens || 512``
    # behavior, then cap the local Ollama call to avoid unbounded generations.
    selected = request.get("max_tokens") or request.get("max_completion_tokens") or 512
    return min(int(selected), 1024)


def _request_temperature(request: Mapping[str, Any]) -> float:
    if "temperature" not in request or request.get("temperature") is None:
        return 0.1
    value = request.get("temperature")
    if not _is_number(value) or float(value) < 0:
        raise RequestValidationError("temperature must be a non-negative number", "temperature")
    # The requested `temperature || 0.1` behavior deliberately maps zero to
    # the stable local default as well.
    return float(value) or 0.1


def build_native_request(request: Any, model: Optional[str] = None) -> Dict[str, Any]:
    """Validate an OpenAI request and build the fixed Ollama request body."""

    if not isinstance(request, dict):
        raise RequestValidationError("request body must be an object")

    selected_model = configured_model() if model is None else model
    request_model = request.get("model")
    if not isinstance(request_model, str) or not request_model:
        raise RequestValidationError("model must be a string", "model")
    if request_model != selected_model:
        raise RequestValidationError("unknown model", "model")

    messages = convert_messages(request.get("messages"))
    native: Dict[str, Any] = {
        "model": selected_model,
        "messages": messages,
        "stream": True,
        "think": False,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": _request_num_predict(request),
            "temperature": _request_temperature(request),
            "num_thread": OLLAMA_NUM_THREADS,
        },
    }

    if "tools" in request:
        native["tools"] = _validate_tools(request["tools"])

    if "stream" in request and not isinstance(request["stream"], bool):
        raise RequestValidationError("stream must be a boolean", "stream")

    return native


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _error_payload(message: str, error_type: str, param: Optional[str] = None) -> Dict[str, Any]:
    error: Dict[str, Any] = {"message": message, "type": error_type}
    if param is not None:
        error["param"] = param
    return {"error": error}


def _upstream_request(url: str, method: str, body: Optional[bytes] = None) -> Any:
    """Open only a fixed URL, using an opener that ignores proxy env vars."""

    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    # Do not use urlopen: ProxyHandler({}) makes the loopback adapter immune to
    # HTTP(S)_PROXY/ALL_PROXY settings in the surrounding container.
    opener = build_opener(ProxyHandler({}))
    try:
        response = opener.open(request, timeout=UPSTREAM_TIMEOUT_SECONDS)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise UpstreamError()

    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        status = getcode() if callable(getcode) else 200
    if not isinstance(status, int) or status < 200 or status >= 300:
        try:
            response.close()
        except Exception:
            pass
        raise UpstreamError()
    return response


def _read_tags() -> None:
    """Touch only Ollama's fixed tags endpoint; model selection stays static."""

    response = _upstream_request(UPSTREAM_TAGS_URL, "GET")
    try:
        # Read a bounded amount.  The response is intentionally not used to
        # discover or select models: /v1/models exposes only OLLAMA_MODEL.
        payload = response.read(MAX_REQUEST_BODY_BYTES + 1)
        if len(payload) > MAX_REQUEST_BODY_BYTES:
            raise UpstreamError()
        json.loads(payload.decode("utf-8"))
    except UpstreamError:
        raise
    except (UnicodeDecodeError, ValueError, TypeError, OSError):
        raise UpstreamError()
    finally:
        try:
            response.close()
        except Exception:
            pass


def _usage(native_done: Mapping[str, Any]) -> Dict[str, int]:
    prompt = native_done.get("prompt_eval_count", 0)
    completion = native_done.get("eval_count", 0)
    prompt_count = prompt if isinstance(prompt, int) and not isinstance(prompt, bool) and prompt >= 0 else 0
    completion_count = (
        completion
        if isinstance(completion, int) and not isinstance(completion, bool) and completion >= 0
        else 0
    )
    return {
        "prompt_tokens": prompt_count,
        "completion_tokens": completion_count,
        "total_tokens": prompt_count + completion_count,
    }


def _argument_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return "{}"


class ToolCallState:
    def __init__(self, call_id: str) -> None:
        self.call_id = call_id
        self.name = ""
        self.arguments = ""
        self.arguments_object: Optional[Dict[str, Any]] = None

    def update(self, function: Mapping[str, Any]) -> str:
        name = function.get("name")
        if isinstance(name, str) and name:
            self.name = name
        value = function.get("arguments", {})
        if isinstance(value, dict):
            if self.arguments_object is None:
                self.arguments_object = {}
            self.arguments_object.update(copy.deepcopy(value))
            self.arguments = _argument_text(self.arguments_object)
        elif isinstance(value, str):
            # Native Ollama normally sends a complete object.  Accommodate a
            # fixture or future backend that sends JSON fragments as strings.
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                self.arguments += value
            else:
                if isinstance(parsed, dict):
                    self.arguments_object = parsed
                    self.arguments = _argument_text(parsed)
                else:
                    self.arguments = value
        else:
            self.arguments = _argument_text(value)
        if not self.arguments:
            self.arguments = "{}"
        return self.arguments

    def as_openai(self) -> Dict[str, Any]:
        return {
            "id": self.call_id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments or "{}"},
        }


class CompletionState:
    def __init__(self) -> None:
        self.content = ""
        self.tool_calls: Dict[int, ToolCallState] = {}

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    def process_message(self, message: Mapping[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        content = message.get("content", "")
        content_delta = content if isinstance(content, str) else ""
        if content_delta:
            self.content += content_delta

        raw_calls = message.get("tool_calls", [])
        if raw_calls is None:
            raw_calls = []
        if not isinstance(raw_calls, list):
            raise UpstreamError()

        deltas: List[Dict[str, Any]] = []
        for list_index, raw_call in enumerate(raw_calls):
            if not isinstance(raw_call, dict):
                raise UpstreamError()
            raw_index = raw_call.get("index", list_index)
            index = raw_index if isinstance(raw_index, int) and not isinstance(raw_index, bool) and raw_index >= 0 else list_index
            function = raw_call.get("function")
            if not isinstance(function, dict):
                raise UpstreamError()

            state = self.tool_calls.get(index)
            if state is None:
                supplied_id = raw_call.get("id")
                call_id = supplied_id if isinstance(supplied_id, str) and supplied_id else f"call_{uuid.uuid4().hex}"
                state = ToolCallState(call_id)
                self.tool_calls[index] = state
            args = state.update(function)
            deltas.append(
                {
                    "index": index,
                    "id": state.call_id,
                    "type": "function",
                    "function": {"name": state.name, "arguments": args},
                }
            )
        return content_delta, deltas

    def openai_tool_calls(self) -> List[Dict[str, Any]]:
        return [self.tool_calls[index].as_openai() for index in sorted(self.tool_calls)]


def _chunk_payload(
    chat_id: str,
    created: int,
    model: str,
    delta: Dict[str, Any],
    finish_reason: Optional[str] = None,
    usage: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    choice: Dict[str, Any] = {"index": 0, "delta": delta, "finish_reason": finish_reason}
    payload: Dict[str, Any] = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [choice],
    }
    if usage is not None:
        payload["usage"] = usage
    return payload


def _completion_payload(
    chat_id: str,
    created: int,
    model: str,
    state: CompletionState,
    native_done: Mapping[str, Any],
) -> Dict[str, Any]:
    message: Dict[str, Any] = {"role": "assistant", "content": state.content}
    calls = state.openai_tool_calls()
    if calls:
        message["tool_calls"] = calls
    return {
        "id": chat_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if calls else "stop",
            }
        ],
        "usage": _usage(native_done),
    }


class OllamaProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # Avoid access logs and, importantly, avoid traceback-like output when a
    # browser/client resets a streaming connection.
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: int, payload: Mapping[str, Any]) -> bool:
        try:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            self.close_connection = True
            return False

    def _send_validation_error(self, error: RequestValidationError) -> None:
        payload = _error_payload(error.message, "invalid_request_error", error.param)
        self._send_json(HTTPStatus.BAD_REQUEST, payload)

    def _send_upstream_error(self) -> None:
        self._send_json(
            HTTPStatus.BAD_GATEWAY,
            _error_payload("Ollama upstream unavailable or returned an invalid response", "upstream_error"),
        )

    def _read_body(self) -> bytes:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise RequestValidationError("Content-Length is required")
        try:
            length = int(raw_length)
        except (TypeError, ValueError):
            raise RequestValidationError("Content-Length is invalid")
        if length < 0:
            raise RequestValidationError("Content-Length is invalid")
        if length > MAX_REQUEST_BODY_BYTES:
            raise RequestValidationError("request body is too large")
        body = self.rfile.read(length)
        if len(body) != length:
            raise RequestValidationError("request body is incomplete")
        return body

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return

        if self.path == "/v1/models":
            try:
                _read_tags()
            except UpstreamError:
                self._send_upstream_error()
                return
            model = configured_model()
            self._send_json(
                HTTPStatus.OK,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": model,
                            "object": "model",
                            "created": 0,
                            "owned_by": "ollama",
                        }
                    ],
                },
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, _error_payload("route not found", "not_found"))

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._send_json(HTTPStatus.NOT_FOUND, _error_payload("route not found", "not_found"))
            return

        try:
            body = self._read_body()
            try:
                request = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise RequestValidationError("request body must be valid JSON")
            if not isinstance(request, dict):
                raise RequestValidationError("request body must be an object")

            native_request = build_native_request(request, configured_model())
            print("ollama-adapter request: messages=%d text_chars=%d tools=%d tool_chars=%d max_output=%d threads=%d" % (
                len(native_request["messages"]),
                sum(len(str(m.get("content", ""))) for m in native_request["messages"]),
                len(native_request.get("tools", [])),
                len(json.dumps(native_request.get("tools", []))),
                native_request["options"]["num_predict"], native_request["options"]["num_thread"]), flush=True)
            response = _upstream_request(UPSTREAM_CHAT_URL, "POST", _json_bytes(native_request))
            try:
                if request.get("stream", False):
                    self._stream_response(response, configured_model())
                else:
                    self._nonstream_response(response, configured_model())
            finally:
                try:
                    response.close()
                except Exception:
                    pass
        except RequestValidationError as error:
            self._send_validation_error(error)
        except UpstreamError:
            self._send_upstream_error()
        except ClientDisconnected:
            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            self.close_connection = True
        except Exception:
            # Keep the protocol response structured and never leak an internal
            # traceback, URL, environment value, or request contents.
            self._send_upstream_error()

    def _send_sse(self, payload: Mapping[str, Any]) -> None:
        line = b"data: " + _json_bytes(payload) + b"\n\n"
        try:
            self.wfile.write(line)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            self.close_connection = True
            raise ClientDisconnected()

    def _stream_response(self, response: Any, model: str) -> None:
        chat_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        state = CompletionState()
        role_sent = False
        saw_done = False

        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            for raw_line in self._iter_ndjson(response):
                if not raw_line.strip():
                    continue
                try:
                    native = json.loads(raw_line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise UpstreamError()
                if not isinstance(native, dict):
                    raise UpstreamError()
                if native.get("error") is not None:
                    raise UpstreamError()

                message = native.get("message")
                if message is None:
                    message = {}
                if not isinstance(message, dict):
                    raise UpstreamError()

                # Ollama may expose Qwen reasoning in message.thinking or a
                # reasoning field.  Deliberately inspect only content and tool
                # calls; reasoning is never copied to OpenAI content.
                content_delta, tool_deltas = state.process_message(message)
                delta: Dict[str, Any] = {}
                if not role_sent:
                    delta["role"] = "assistant"
                    role_sent = True
                if content_delta:
                    delta["content"] = content_delta
                if tool_deltas:
                    delta["tool_calls"] = tool_deltas
                if delta:
                    self._send_sse(_chunk_payload(chat_id, created, model, delta))

                if native.get("done") is True:
                    saw_done = True
                    finish_reason = "tool_calls" if state.has_tool_calls else "stop"
                    self._send_sse(
                        _chunk_payload(
                            chat_id,
                            created,
                            model,
                            {},
                            finish_reason=finish_reason,
                            usage=_usage(native),
                        )
                    )
                    self._send_done_marker()
                    break

            if not saw_done:
                raise UpstreamError()
        except ClientDisconnected:
            raise
        except UpstreamError:
            # SSE headers were sent before reading the first native line, so
            # report a structured event rather than attempting a second HTTP
            # status line.
            try:
                self._send_sse(
                    _error_payload(
                        "Ollama upstream unavailable or returned an invalid response",
                        "upstream_error",
                    )
                )
            except ClientDisconnected:
                pass

    def _send_done_marker(self) -> None:
        try:
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            self.close_connection = True
            raise ClientDisconnected()

    @staticmethod
    def _iter_ndjson(response: Any) -> Iterable[bytes]:
        while True:
            line = response.readline()
            if not line:
                return
            yield line

    def _nonstream_response(self, response: Any, model: str) -> None:
        state = CompletionState()
        native_done: Optional[Mapping[str, Any]] = None
        for raw_line in self._iter_ndjson(response):
            if not raw_line.strip():
                continue
            try:
                native = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise UpstreamError()
            if not isinstance(native, dict):
                raise UpstreamError()
            if native.get("error") is not None:
                raise UpstreamError()
            message = native.get("message") or {}
            if not isinstance(message, dict):
                raise UpstreamError()
            # process_message intentionally drops thinking/reasoning fields.
            state.process_message(message)
            if native.get("done") is True:
                native_done = native
                break

        if native_done is None:
            raise UpstreamError()

        payload = _completion_payload(
            f"chatcmpl-{uuid.uuid4().hex}", int(time.time()), model, state, native_done
        )
        self._send_json(HTTPStatus.OK, payload)


def main() -> None:
    # No host/port CLI override: this is intentionally a loopback-only shim.
    server = ThreadingHTTPServer((HOST, PORT), OllamaProxyHandler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
