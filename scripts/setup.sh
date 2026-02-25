#!/bin/bash
set -e
echo "🤖 QuantAI 环境安装..."

cd "$(dirname "$0")/.."

echo "📦 安装后端依赖..."
cd backend
pip3 install -r requirements.txt
cd ..

echo "📦 安装前端依赖..."
cd frontend
npm install
cd ..

echo "✅ 安装完成！运行 scripts/start.sh 启动系统"
