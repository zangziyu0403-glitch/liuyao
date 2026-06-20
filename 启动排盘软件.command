#!/bin/zsh
cd "$(dirname "$0")"

PYTHON_BIN="/usr/local/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "没有找到 python3，请先安装 Python。"
  read -r "?按回车退出"
  exit 1
fi

"$PYTHON_BIN" app.py &
SERVER_PID=$!

sleep 1
open "http://127.0.0.1:8000"

wait "$SERVER_PID"
