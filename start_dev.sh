#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"
BACKEND_LOG="${SCRIPT_DIR}/.dev-backend.log"

case "${OSTYPE:-}" in
  msys*|cygwin*|win32*) PYTHONPATH_SEP=';' ;;
  *) PYTHONPATH_SEP=':' ;;
esac

if [[ -n "${BACKTEST_VENV_ACTIVATE:-}" ]]; then
  echo "使用虚拟环境脚本: ${BACKTEST_VENV_ACTIVATE}"
  # shellcheck disable=SC1090
  source "${BACKTEST_VENV_ACTIVATE}"
fi

if ! command -v python >/dev/null 2>&1; then
  echo "未找到 python，请先安装 Python 或激活虚拟环境。"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 npm，请先安装 Node.js。"
  exit 1
fi

if ! python -c "import uvicorn, fastapi" >/dev/null 2>&1; then
  echo "当前 Python 环境缺少后端依赖，请先执行："
  echo "pip install -r ${SCRIPT_DIR}/backend/requirements.txt"
  exit 1
fi

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  echo "检测到前端依赖未安装，正在执行 npm install..."
  (
    cd "${FRONTEND_DIR}"
    npm install
  )
fi

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "启动后端服务..."
(
  cd "${PROJECT_ROOT}"
  PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+${PYTHONPATH_SEP}${PYTHONPATH}}" \
    python -m uvicorn event_driven_backtest.backend.api.server:app --reload --host "${BACKEND_HOST}" --port "${BACKEND_PORT}"
) >"${BACKEND_LOG}" 2>&1 &
BACKEND_PID=$!

sleep 2
if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
  echo "后端启动失败，请查看日志：${BACKEND_LOG}"
  tail -n 50 "${BACKEND_LOG}" || true
  exit 1
fi

echo "后端已启动: http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "Swagger 文档: http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
echo "后端日志: ${BACKEND_LOG}"
echo "启动前端服务..."

cd "${FRONTEND_DIR}"
exec npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}"
