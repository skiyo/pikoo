#!/usr/bin/env bash
# Access must already have been granted by BAAI. Never place a token in this file.
set -euo pipefail
umask 077
: "${HF_TOKEN_PATH:?Set HF_TOKEN_PATH to a private file containing your authorized read token}"
test -r "$HF_TOKEN_PATH"
export HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}"
export HF_HUB_DISABLE_XET=1
export HF_HUB_DOWNLOAD_TIMEOUT=60
# Respect the operator's proxy settings. Custom endpoints are opt-in.
hf download BAAI/ChildMandarin \
  new_data/train.tar new_data/dev.tar new_data/test.tar README.md \
  --repo-type dataset --revision 67a5579247989e071911b2e8d72952c2afd43ca3 \
  --local-dir "${1:-training/data/childmandarin-original}" --max-workers 3
