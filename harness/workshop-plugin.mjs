import { spawn } from 'node:child_process'
import { Buffer } from 'node:buffer'
import { defineTool } from '/opt/pentest-harness/apps/cli/node_modules/@pentest-harness/dsh-tools/lib/index.js'

export const name = 'academy-workshop-plugin'
export const inject = ['tools']

const HELPER = '/usr/local/bin/lab-harness-tools'
const HELPER_CWD = '/opt/academy-harness'
const MAX_INPUT_BYTES = 32 * 1024
const MAX_OUTPUT_BYTES = 80 * 1024
const MAX_STDERR_BYTES = 16 * 1024
const HELPER_TIMEOUT_MS = 80_000
const ALLOWED_TOOLS = new Set(['lab_discover', 'lab_missions', 'lab_progress', 'lab_http', 'lab_submit', 'skill'])
const SERVICES = new Set(['target', 'receiver', 'mailpit', 'academy', 'ollama'])
const DISCOVER_SERVICES = new Set([...SERVICES, 'all'])
const METHODS = new Set(['GET', 'POST', 'PUT'])
const MISSION_KEYS = new Set(['mission_id', 'request'])
const REQUEST_KEYS = new Set(['method', 'params', 'headers', 'body', 'content_type'])
const DISCOVER_KEYS = new Set(['service'])
const MISSIONS_KEYS = new Set(['mission_id', 'family', 'limit', 'offset'])
const MAX_MISSION_LIST = 32
const SKILL_KEYS = new Set(['name'])
const SKILL_NAMES = new Set([
  'vulnerableapp-scope',
  'vulnerableapp-http',
  'vulnerableapp-evidence',
])
const KEY_RE = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/
const encoder = new TextEncoder()

const REQUEST_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: true,
  properties: {
    method: { type: 'string', required: true, enum: [...METHODS] },
    params: {
      type: 'object',
      required: true,
      additionalProperties: true,
      description: 'Query/form values. Keys and values are strings; the server catalog fixes the route.',
    },
    headers: {
      type: 'object',
      required: true,
      additionalProperties: true,
      description: 'Request headers. Host, proxy and framing headers are ignored by the helper.',
    },
    body: {
      required: true,
      oneOf: [{ type: 'string' }, { type: 'null' }],
    },
    content_type: {
      oneOf: [{ type: 'string' }, { type: 'null' }],
      description: 'Optional Content-Type header passed to the fixed helper.',
    },
  },
}

const JSON_OUTPUT = {
  schema: { type: 'json' },
  render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
}

function byteLength(value) {
  return encoder.encode(value).byteLength
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function validateUnknownKeys(value, allowed, label) {
  if (!isRecord(value)) return undefined
  const unknown = Object.keys(value).filter(key => !allowed.has(key))
  return unknown.length > 0
    ? `${label} contiene claves no permitidas: ${unknown.join(', ')}`
    : undefined
}

function validateStringRecord(value, label, { header = false } = {}) {
  if (!isRecord(value)) return `${label} debe ser un objeto`
  const entries = Object.entries(value)
  if (entries.length > 64) return `${label} supera el máximo de 64 entradas`
  for (const [key, item] of entries) {
    if (!KEY_RE.test(key)) return `${label} contiene una clave inválida`
    if (typeof item !== 'string') return `${label}.${key} debe ser string`
    if (item.length > 16 * 1024 || byteLength(item) > 16 * 1024) return `${label}.${key} excede 16 KiB`
    if (header && /[\r\n\0]/u.test(key)) return `${label}.${key} contiene CR, LF o NUL`
    if (header && /[\r\n\0]/u.test(item)) return `${label}.${key} contiene CR, LF o NUL`
  }
  return undefined
}

function validateRequest(request) {
  if (!isRecord(request)) return 'request debe ser un objeto'
  const unknown = validateUnknownKeys(request, REQUEST_KEYS, 'request')
  if (unknown) return unknown
  if (typeof request.method !== 'string' || !METHODS.has(request.method)) {
    return 'request.method no está permitido'
  }
  const paramsError = validateStringRecord(request.params, 'request.params')
  if (paramsError) return paramsError
  const headersError = validateStringRecord(request.headers, 'request.headers', { header: true })
  if (headersError) return headersError
  for (const key of Object.keys(request.headers)) {
    const lower = key.toLowerCase()
    if (lower === 'host' || lower === 'connection' || lower === 'content-length' || lower === 'transfer-encoding'
      || lower === 'proxy-authorization' || lower === 'proxy-connection' || lower.startsWith('proxy-')) {
      return `request.headers.${key} está reservado`
    }
  }
  if (request.body !== null && typeof request.body !== 'string') return 'request.body debe ser string o null'
  if (typeof request.body === 'string' && byteLength(request.body) > 16 * 1024) return 'request.body excede 16 KiB'
  if (request.content_type !== undefined && request.content_type !== null) {
    if (typeof request.content_type !== 'string' || request.content_type.length === 0
      || byteLength(request.content_type) > 256) {
      return 'request.content_type no es válido'
    }
    if (/[\r\n\0]/u.test(request.content_type)) return 'request.content_type contiene CR, LF o NUL'
  }
  return undefined
}

function validateMission(args) {
  if (!isRecord(args) || typeof args.mission_id !== 'string' || !KEY_RE.test(args.mission_id)) {
    return 'mission_id debe ser un identificador allowlisted'
  }
  const unknown = validateUnknownKeys(args, MISSION_KEYS, 'arguments')
  if (unknown) return unknown
  return validateRequest(args.request)
}

function validateMissions(args) {
  if (!isRecord(args)) return 'lab_missions requiere un objeto'
  const unknown = validateUnknownKeys(args, MISSIONS_KEYS, 'lab_missions')
  if (unknown) return unknown
  if (args.mission_id !== undefined && (typeof args.mission_id !== 'string' || !KEY_RE.test(args.mission_id))) {
    return 'lab_missions.mission_id no está allowlisted'
  }
  if (args.family !== undefined && (typeof args.family !== 'string' || !/^[A-Za-z0-9_.-]+$/.test(args.family))) {
    return 'lab_missions.family no es válida'
  }
  if (args.limit !== undefined && (!Number.isInteger(args.limit) || args.limit < 1 || args.limit > MAX_MISSION_LIST)) {
    return `lab_missions.limit debe estar entre 1 y ${MAX_MISSION_LIST}`
  }
  if (args.offset !== undefined && (!Number.isInteger(args.offset) || args.offset < 0 || args.offset > 256)) {
    return 'lab_missions.offset debe estar entre 0 y 256'
  }
  if (args.mission_id !== undefined && (args.family !== undefined || args.limit !== undefined || args.offset !== undefined)) {
    return 'lab_missions.mission_id no se combina con filtros o paginación'
  }
  return undefined
}

function validateProgress(args) {
  if (!isRecord(args)) return 'lab_progress requiere un objeto vacío'
  return Object.keys(args).length === 0 ? undefined : 'lab_progress no acepta argumentos'
}

function validateHelperReply(action, reply) {
  if (!isRecord(reply) || reply.action !== action || typeof reply.ok !== 'boolean') {
    throw new Error(`lab helper devolvió un sobre inválido para ${action}`)
  }
  return reply
}

function safeEnvironment() {
  // The helper owns all lab credentials and service addresses. Do not forward
  // the harness environment wholesale into the child process.
  return {
    PATH: '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    HOME: '/home/kali',
    USER: 'kali',
    LANG: 'C.UTF-8',
    LC_ALL: 'C.UTF-8',
    OLLAMA_DUMMY_API_KEY: 'ollama-local-only',
  }
}

function runHelper(action, payload, signal) {
  const serialized = JSON.stringify(payload)
  if (byteLength(serialized) > MAX_INPUT_BYTES) {
    return Promise.reject(new Error('entrada del helper excede 32 KiB'))
  }
  if (signal?.aborted) return Promise.reject(new Error('operación cancelada antes de iniciar'))
  return new Promise((resolve, reject) => {
    const child = spawn(HELPER, [action], {
      cwd: HELPER_CWD,
      shell: false,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: safeEnvironment(),
    })
    let stdout = Buffer.alloc(0)
    let stderr = Buffer.alloc(0)
    let settled = false
    let timer
    let killTimer

    const finishError = (error) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
      reject(error instanceof Error ? error : new Error(String(error)))
    }
    const terminate = (reason) => {
      if (settled) return
      child.kill('SIGTERM')
      killTimer = setTimeout(() => child.kill('SIGKILL'), 1_000)
      finishError(new Error(reason))
    }
    const onAbort = () => terminate('operación cancelada')

    child.on('error', (error) => finishError(new Error(`no se pudo iniciar lab-harness-tools: ${error.message}`)))
    child.stdout.on('data', (chunk) => {
      if (settled) return
      stdout = Buffer.concat([stdout, chunk])
      if (stdout.byteLength > MAX_OUTPUT_BYTES) terminate('salida del helper excede 80 KiB')
    })
    child.stderr.on('data', (chunk) => {
      if (stderr.byteLength < MAX_STDERR_BYTES) {
        stderr = Buffer.concat([stderr, chunk]).subarray(0, MAX_STDERR_BYTES)
      }
    })
    child.on('close', (code, childSignal) => {
      if (settled) return
      clearTimeout(timer)
      clearTimeout(killTimer)
      signal?.removeEventListener('abort', onAbort)
      if (code !== 0) {
        const suffix = stderr.byteLength > 0 ? `: ${stderr.toString('utf8').slice(0, 512)}` : ''
        finishError(new Error(`lab-harness-tools terminó con código ${String(code)}${childSignal ? ` (${childSignal})` : ''}${suffix}`))
        return
      }
      let reply
      try {
        reply = JSON.parse(stdout.toString('utf8'))
      } catch {
        finishError(new Error('lab-harness-tools no devolvió JSON válido'))
        return
      }
      try {
        const validated = validateHelperReply(action, reply)
        settled = true
        clearTimeout(killTimer)
        resolve(validated)
      } catch (error) {
        finishError(error)
      }
    })
    signal?.addEventListener('abort', onAbort, { once: true })
    timer = setTimeout(() => terminate('lab-harness-tools excedió 80 segundos'), HELPER_TIMEOUT_MS)
    child.stdin.end(serialized)
  })
}

function registerTools(ctx) {
  ctx.tools.register(defineTool({
      name: 'lab_discover',
      description: 'Descubre únicamente un servicio fijo del laboratorio local. No acepta hosts, puertos ni URLs del modelo.',
      parameters: {
        service: { type: 'string', required: true, enum: [...DISCOVER_SERVICES] },
      },
    output: JSON_OUTPUT,
    async execute(args, exec) {
      return await runHelper('discover', { service: args.service }, exec.signal)
    },
    isConcurrencySafe: () => true,
  }))

  ctx.tools.register(defineTool({
    name: 'lab_missions',
    description: 'Lee el catálogo fijo local: lista misiones o muestra la receta exacta de un mission_id. No acepta rutas, URLs ni comandos.',
    parameters: {
      mission_id: { type: 'string', description: 'ID exacto del catálogo; omitir para listar.' },
      family: { type: 'string', description: 'Filtro de familia allowlisted del catálogo.' },
      limit: { type: 'integer', description: 'Máximo 32 misiones por página.' },
      offset: { type: 'integer', description: 'Desplazamiento entre 0 y 256.' },
    },
    output: JSON_OUTPUT,
    async execute(args, exec) {
      return await runHelper('missions', args ?? {}, exec.signal)
    },
    isConcurrencySafe: () => true,
  }))

  ctx.tools.register(defineTool({
    name: 'lab_progress',
    description: 'Lee score, misiones completadas y eventos recientes desde la sesión local de lab y Academy. No envía intentos.',
    parameters: {},
    output: JSON_OUTPUT,
    async execute(_args, exec) {
      return await runHelper('progress', {}, exec.signal)
    },
    isConcurrencySafe: () => true,
  }))

  for (const [name, action, description] of [
    ['lab_http', 'http', 'Envía una solicitud HTTP al endpoint fijo de la misión y devuelve evidencia acotada del servidor; nunca acepta una ruta arbitraria.'],
    ['lab_submit', 'submit', 'Envía una solicitud de misión al backend autorizado para evaluación y devuelve únicamente el resultado de puntuación/evidencia producido por el servidor.'],
  ]) {
    ctx.tools.register(defineTool({
      name,
      description,
      parameters: {
        mission_id: { type: 'string', required: true, description: 'ID exacto de misión del catálogo del laboratorio.' },
        request: REQUEST_SCHEMA,
      },
      output: JSON_OUTPUT,
      async execute(args, exec) {
        return await runHelper(action, { mission_id: args.mission_id, request: args.request }, exec.signal)
      },
      isConcurrencySafe: () => false,
    }))
  }
}

function sensitiveApprovalKey(key) {
  const compact = String(key ?? '').toLowerCase().replace(/[^a-z0-9]/g, '')
  return ['password', 'passwd', 'pwd', 'authorization', 'cookie', 'setcookie', 'token', 'secret', 'apikey', 'credential', 'session', 'jwt', 'bearer']
    .some(token => compact.includes(token))
}

function sanitizeApprovalValue(value, key, depth = 0) {
  if (sensitiveApprovalKey(key)) return '<redacted>'
  if (depth > 4) return '<nested value omitted>'
  if (typeof value === 'string') {
    return value
      .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer <redacted>')
      .replace(/(password|passwd|pwd|authorization|cookie|set-cookie|token|secret|api[_-]?key)\s*([:=])\s*(['"]?)[^'"\s,;&}]+/gi, '$1$2$3<redacted>')
      .slice(0, 512)
  }
  if (Array.isArray(value)) return value.slice(0, 8).map(item => sanitizeApprovalValue(item, undefined, depth + 1))
  if (isRecord(value)) {
    return Object.fromEntries(Object.entries(value).slice(0, 16).map(([itemKey, item]) => [
      itemKey.slice(0, 128), sanitizeApprovalValue(item, itemKey, depth + 1),
    ]))
  }
  return value
}

function approvalReason(exec) {
  const args = isRecord(exec.arguments) ? exec.arguments : {}
  let detail
  if (exec.name === 'lab_discover') {
    detail = { service: args.service }
  } else if (exec.name === 'lab_missions') {
    detail = {
      mission_id: args.mission_id,
      family: args.family,
      limit: args.limit,
      offset: args.offset,
    }
  } else if (exec.name === 'lab_progress') {
    detail = { session: 'lab local; solo lectura' }
  } else {
    const request = isRecord(args.request) ? args.request : {}
    detail = {
      mission_id: args.mission_id,
      method: request.method,
      params: sanitizeApprovalValue(request.params ?? {}, 'params'),
      header_names: isRecord(request.headers) ? Object.keys(request.headers).slice(0, 32) : [],
      body: request.body === null || request.body === undefined ? null : '<body present; values not shown>',
    }
  }
  let encoded
  try {
    encoded = JSON.stringify(sanitizeApprovalValue(detail))
  } catch {
    encoded = '{"detail":"unavailable"}'
  }
  return `Aprobación única para ${exec.name}; no se reutiliza: ${encoded.slice(0, 1_400)}`
}

function guardReason(exec) {
  if (!ALLOWED_TOOLS.has(exec.name)) {
    return `herramienta no allowlisted: ${exec.name}`
  }
  if (exec.name === 'skill') {
    const args = exec.arguments
    const unknown = validateUnknownKeys(args, SKILL_KEYS, 'skill')
    if (unknown) return unknown
    return !isRecord(args) || typeof args.name !== 'string' || !SKILL_NAMES.has(args.name)
      ? 'skill.name no está allowlisted'
      : undefined
  }
  if (exec.name === 'lab_discover') {
    const args = exec.arguments
    const unknown = validateUnknownKeys(args, DISCOVER_KEYS, 'lab_discover')
    if (unknown) return unknown
    return !isRecord(args) || typeof args.service !== 'string' || !DISCOVER_SERVICES.has(args.service)
      ? 'lab_discover.service inválido'
      : undefined
  }
  if (exec.name === 'lab_missions') return validateMissions(exec.arguments)
  if (exec.name === 'lab_progress') return validateProgress(exec.arguments)
  return validateMission(exec.arguments)
}

async function approvalGate(exec, next) {
  const guard = guardReason(exec)
  if (guard !== undefined) return { kind: 'deny', reason: guard }
  const decision = await next()
  if (decision.kind !== 'allow') return decision
  if (exec.agent === undefined) {
    return { kind: 'deny', reason: `la herramienta ${exec.name} requiere aprobación explícita disponible en la UI` }
  }
  const approval = exec.agent.ctx.get('approval')
  if (approval === undefined) {
    return { kind: 'deny', reason: `la herramienta ${exec.name} requiere aprobación explícita disponible en la UI` }
  }
  const outcome = await approval.request({
    agent: exec.agent,
    toolName: exec.name,
    callId: exec.callId,
    reason: approvalReason(exec),
    signal: exec.signal,
  })
  if (outcome === 'allowed-once') return { kind: 'allow' }
  if (outcome === 'rejected') return { kind: 'deny', reason: `la persona rechazó ${exec.name}` }
  if (outcome === 'cancelled') return { kind: 'deny', reason: `la aprobación de ${exec.name} fue cancelada` }
  return { kind: 'deny', reason: `la aprobación de ${exec.name} no está disponible` }
}

export function apply(ctx) {
  registerTools(ctx)
  // guards are ordered after the extensible pre-execute waterfall by the
  // runtime, so they remain monotonic even if another plugin returns allow.
  ctx.tools.guard(guardReason)
  ctx.on('tools/pre-execute', (exec, next) => approvalGate(exec, next), { prepend: true })
}
