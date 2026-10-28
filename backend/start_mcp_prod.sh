#!/bin/bash
# ARL-Next 容器内 MCP 远程异步服务启动脚本

set -e

echo "🚀 等待数据库就绪..."
/usr/bin/wait-for-it.sh mongodb:27017 -t 60

cd /code/backend
source /code/backend/.venv-docker/bin/activate

# 确保配置源就绪 (支持 config.yaml 或 config.yaml.example 模板生成)
CONFIG_SRC=/code/backend/config.yaml
if [ ! -f "$CONFIG_SRC" ]; then
    CONFIG_SRC=/code/backend/config.yaml.example
fi
cp "$CONFIG_SRC" /tmp/config.yaml.tmp
sed -i 's/127.0.0.1:27018/mongodb:27017/g' /tmp/config.yaml.tmp
sed -i 's/127.0.0.1:5673/rabbitmq:5672/g' /tmp/config.yaml.tmp
cp -f /tmp/config.yaml.tmp /code/backend/app/config.yaml
rm -f /tmp/config.yaml.tmp

echo "🚀 正在启动 ARL-Next 原生异步 MCP SSE 服务 (端口 5005)..."
python3 -m app.mcp_server --host 0.0.0.0 --port 5005
