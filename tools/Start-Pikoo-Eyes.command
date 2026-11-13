#!/bin/zsh
set -eu
base="${0:A:h}"
if ! bash "$base/start-dualeye.sh"; then
  echo 'Start failed. Review the error above. Press Enter to close.'
  read answer
  exit 1
fi
