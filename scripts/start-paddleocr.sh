#!/usr/bin/env bash
# Run PaddleOCR-VL-1.6 with both GGUF files (main + mmproj).
# LM Studio often fails if you load only the CLIP/mmproj file.
set -euo pipefail

MODEL_DIR="${PADDLEOCR_MODEL_DIR:-$HOME/.lmstudio/models/PaddlePaddle/PaddleOCR-VL-1.6-GGUF}"
MAIN="$MODEL_DIR/PaddleOCR-VL-1.6-GGUF.gguf"
MMPROJ="$MODEL_DIR/PaddleOCR-VL-1.6-GGUF-mmproj.gguf"
PORT="${PADDLEOCR_PORT:-1240}"
LOG="${PADDLEOCR_LOG:-/tmp/paddleocr-vl.log}"

if [[ ! -f "$MAIN" ]]; then
  echo "Missing main model: $MAIN" >&2
  echo "Download PaddleOCR-VL-1.6-GGUF.gguf into that folder (not only the mmproj)." >&2
  exit 1
fi
if [[ ! -f "$MMPROJ" ]]; then
  echo "Missing mmproj: $MMPROJ" >&2
  exit 1
fi

if curl -sf "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; then
  echo "Already listening on http://127.0.0.1:${PORT}"
  exit 0
fi

echo "Starting PaddleOCR-VL on :${PORT}"
echo "  main   $MAIN"
echo "  mmproj $MMPROJ"
nohup llama-server \
  -m "$MAIN" \
  --mmproj "$MMPROJ" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --ctx-size 8192 \
  -n 2048 \
  --temp 0 \
  --jinja \
  >"$LOG" 2>&1 &
echo $! > /tmp/paddleocr-vl.pid
sleep 3
if curl -sf "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; then
  echo "Ready: http://127.0.0.1:${PORT}/v1"
  echo "Point the app at it with:"
  echo "  LLM_PROVIDER=lmstudio"
  echo "  LLM_BASE_URL=http://host.docker.internal:${PORT}/v1"
  echo "  LLM_MODEL=paddleocr-vl-1.6"
else
  echo "Server did not become ready. See $LOG" >&2
  tail -40 "$LOG" >&2 || true
  exit 1
fi
