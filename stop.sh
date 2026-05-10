#!/bin/bash
# personKnowledge 快速停止脚本
PID=$(lsof -ti :8765 2>/dev/null)
if [ -z "$PID" ]; then
  echo "ℹ️ personKnowledge 服务未运行"
  exit 0
fi
echo "🛑 停止 personKnowledge 服务 (PID: $PID)..."
kill -9 $PID
echo "✅ 已停止"
