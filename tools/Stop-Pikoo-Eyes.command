#!/bin/zsh
set -eu
base="${0:A:h}"
if ! bash "$base/stop-dualeye.sh"; then
  echo 'Stop failed. Review the error above. Press Enter to close.'
  read answer
  exit 1
fi
