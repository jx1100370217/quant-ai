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

# 准备日志目录（每次启动覆盖旧日志，便于 tail -f 调试）
mkdir -p logs
: > logs/backend.log
: > logs/frontend.log

# 启动后端（输出重定向到 logs/backend.log，方便排查"周度选股顾问"等长时任务）
echo "📡 启动后端 API (端口 8000)，日志: logs/backend.log"
cd backend
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload \
  > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# 启动前端
echo "🎨 启动前端 (端口 3000)，日志: logs/frontend.log"
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# 等待端口监听就绪（最多 30s）—— 让用户拿到的是 "已启动" 而不是空壳
echo "⏳ 等待服务就绪..."
for i in $(seq 1 60); do
  BACK_OK=0; FRONT_OK=0
  lsof -ti:8000 >/dev/null 2>&1 && BACK_OK=1
  lsof -ti:3000 >/dev/null 2>&1 && FRONT_OK=1
  [ "$BACK_OK" = "1" ] && [ "$FRONT_OK" = "1" ] && break
  sleep 0.5
done

echo ""
if [ "$BACK_OK" = "1" ] && [ "$FRONT_OK" = "1" ]; then
  echo "✅ QuantAI 已启动!"
else
  echo "⚠️  服务启动超时，请检查日志："
  [ "$BACK_OK" != "1" ] && echo "    tail logs/backend.log"
  [ "$FRONT_OK" != "1" ] && echo "    tail logs/frontend.log"
fi
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"
echo ""
echo "实时日志: tail -f logs/backend.log logs/frontend.log"
echo "按 Ctrl+C 停止..."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
