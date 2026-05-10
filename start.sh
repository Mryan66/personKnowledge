#!/bin/bash
# personKnowledge 快速启动脚本
cd "$(dirname "$0")"
echo "🚀 启动 personKnowledge 服务..."
python3 -m app.cli web
