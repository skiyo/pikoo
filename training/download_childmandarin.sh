#!/usr/bin/env bash
# Access must already have been granted by BAAI. Never place a token in this file.
set -euo pipefail
umask 077
: "${HF_TOKEN_PATH:?Set HF_TOKEN_PATH to a private file containing your authorized read token}"
test -r "$HF_TOKEN_PATH"
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1
export HF_HUB_DOWNLOAD_TIMEOUT=60
# This process uses direct network connections, including storage redirects.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY='*' no_proxy='*'
hf download BAAI/ChildMandarin \
  new_data/train.tar new_data/dev.tar new_data/test.tar README.md \
  --repo-type dataset --revision 67a5579247989e071911b2e8d72952c2afd43ca3 \
  --local-dir "${1:-training/data/childmandarin-original}" --max-workers 3
