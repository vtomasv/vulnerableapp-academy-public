#!/bin/sh
set -eu
export DSH_HOME=/home/kali/.local/share/pentest-harness
export DSH_TELEMETRY_DISABLED=1
export OLLAMA_DUMMY_API_KEY=ollama-local-only
export DSH_PERMISSION_MODE=workspace-write
mkdir -p "$DSH_HOME"
python3 - <<'PY'
import json, os, re
from pathlib import Path
model = os.environ.get('OLLAMA_MODEL', 'qwen3:4b')
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:@+-]{0,199}', model) or model.endswith(':cloud'):
    raise SystemExit('OLLAMA_MODEL debe ser una etiqueta local válida, no cloud')
source = Path('/opt/academy-harness/workshop.cordis.patch.yml').read_text()
source = source.replace('__OLLAMA_MODEL__', json.dumps(model))
out = Path(os.environ['DSH_HOME']) / 'workshop.runtime.cordis.patch.yml'
out.write_text(source)
out.chmod(0o600)
PY
cd /home/kali
exec /usr/local/bin/node /opt/pentest-harness/apps/cli/lib/bin.js \
  --profile web --patch "$DSH_HOME/workshop.runtime.cordis.patch.yml" \
  --port 2323 --no-open
