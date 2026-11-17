#!/usr/bin/env bash
# Deploy merged main on the server. The ops workflow runs it through sudo as ec2-user (mode=deploy);
# Claude Code itself is not allowed to. Refuses during market hours and on a dirty or non-main checkout.
set -euo pipefail
cd /opt/trademind/trademind

now=$((10#$(TZ=Asia/Kolkata date +%H%M)))
dow=$(TZ=Asia/Kolkata date +%u)
if [ "$dow" -le 5 ] && [ "$now" -ge 835 ] && [ "$now" -le 1535 ]; then
  echo "Market day between 08:35 and 15:35 IST: the paper run may be live. Deploy after 15:35." >&2
  exit 1
fi
if [ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then
  echo "The server checkout is not on main; fix it by hand." >&2
  exit 1
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "The server checkout has local changes; refusing to deploy." >&2
  exit 1
fi

before=$(git rev-parse --short HEAD)
git pull -q --ff-only origin main
after=$(git rev-parse --short HEAD)
if [ "$before" = "$after" ]; then
  echo "Already at $after; rebuilding anyway."
else
  echo "main: $before -> $after"
  git log --oneline "$before..$after"
fi
docker compose up -d --build db api
docker compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
