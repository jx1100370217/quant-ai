#!/bin/bash
cd "$(dirname "$0")/.."

echo "🤖 启动 QuantAI..."

# 清理残留进程
for PORT in 3000 8000; do
  PIDS=$(lsof -ti:$PORT 2>/dev/null)
  if [ -n "$PIDS" ]; then
    echo "⚠️  端口 $PORT 被占用，正在强制清理..."
    echo "$PIDS" | xargs kill -9 2>/dev/null
  fi
done
# 等待端口完全释放
for i in $(seq 1 20); do
  lsof -ti:3000 >/dev/null 2>&1 || lsof -ti:8000 >/dev/null 2>&1 || break
  sleep 0.5
done

# 启动后端
echo "📡 启动后端 API (端口 8000)..."
cd backend
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# 启动前端
echo "🎨 启动前端 (端口 3000)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ QuantAI 已启动!"
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止..."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
