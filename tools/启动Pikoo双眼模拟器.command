#!/bin/zsh
set -eu
base="${0:A:h}"
if ! bash "$base/start-dualeye.sh"; then
  echo '启动失败，请查看上方提示。按回车关闭。'
  read answer
  exit 1
fi
