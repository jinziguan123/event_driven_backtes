#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

if [[ -n "${BACKTEST_VENV_ACTIVATE:-}" ]]; then
  echo "使用虚拟环境脚本: ${BACKTEST_VENV_ACTIVATE}"
  # shellcheck disable=SC1090
  source "${BACKTEST_VENV_ACTIVATE}"
fi

PYTHON_CMD=()
if command -v python >/dev/null 2>&1; then
  PYTHON_CMD=(python)
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=(python3)
elif command -v py >/dev/null 2>&1; then
  PYTHON_CMD=(py -3)
else
  echo "未找到可用的 Python（python / python3 / py -3），请先安装 Python 或激活虚拟环境。"
  exit 1
fi

if ! "${PYTHON_CMD[@]}" -c "import uvicorn, fastapi" >/dev/null 2>&1; then
  echo "当前 Python 环境缺少后端依赖，请先执行："
  echo "\"${PYTHON_CMD[*]}\" -m pip install -r ${SCRIPT_DIR}/backend/requirements.txt"
  exit 1
fi

echo "启动后端服务: http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "Swagger 文档: http://${BACKEND_HOST}:${BACKEND_PORT}/docs"

cd "${PROJECT_ROOT}"
exec "${PYTHON_CMD[@]}" -m uvicorn event_driven_backtest.backend.api.server:app \
  --reload \
  --host "${BACKEND_HOST}" \
  --port "${BACKEND_PORT}"
