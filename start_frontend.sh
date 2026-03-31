#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"

NPM_CMD=()
if command -v npm >/dev/null 2>&1; then
  NPM_CMD=(npm)
elif command -v npm.cmd >/dev/null 2>&1; then
  NPM_CMD=(npm.cmd)
else
  echo "未找到可用的 npm（npm / npm.cmd），请先安装 Node.js。"
  exit 1
fi

if [[ ! -d "${FRONTEND_DIR}" ]]; then
  echo "未找到前端目录: ${FRONTEND_DIR}"
  exit 1
fi

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  echo "检测到前端依赖未安装，正在执行 npm install..."
  (
    cd "${FRONTEND_DIR}"
    "${NPM_CMD[@]}" install
  )
fi

echo "启动前端服务: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "说明: 当前 Vite 代理默认转发 /api 到 http://127.0.0.1:8000"

cd "${FRONTEND_DIR}"
exec "${NPM_CMD[@]}" run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}"
