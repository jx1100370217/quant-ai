#!/bin/bash
echo "🛑 停止 QuantAI..."

for PORT in 3000 8000; do
  PIDS=$(lsof -ti:$PORT 2>/dev/null)
  if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs kill -9 2>/dev/null
    echo "✅ 端口 $PORT 已停止"
  else
    echo "⚠️  端口 $PORT 未运行"
  fi
done

# 等待端口完全释放
for i in $(seq 1 20); do
  if ! lsof -ti:3000 >/dev/null 2>&1 && ! lsof -ti:8000 >/dev/null 2>&1; then
    echo ""
    echo "🏁 QuantAI 已停止"
    exit 0
  fi
  sleep 0.5
done

echo "⚠️  部分端口未能释放，请手动检查"
