#!/bin/bash
# 启动启用前端构建产物的 personKnowledge 服务
cd "$(dirname "$0")"
echo "🚀 启动 personKnowledge 服务（启用 frontend/dist 资源）..."
KB_FRONTEND_ASSETS=true python3 -m app.cli web
