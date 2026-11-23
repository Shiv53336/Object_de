#!/usr/bin/env bash
# One-time root setup of the ops agent on the TRADEMIND server (Amazon Linux 2023, arm64).
#
#   sudo RUNNER_TOKEN=<token> bash /opt/trademind/trademind/deploy/agent/setup.sh
#
# RUNNER_TOKEN comes from GitHub: repo Settings > Actions > Runners > New self-hosted runner
# (the token in the ./config.sh line; it is valid for one hour). Re-running is safe.
#
# What it sets up (docs/AGENT.md explains why):
#   - an `agent` Linux user, outside the docker group, that cannot read the production .env or data/
#   - a firewall rule so `agent` cannot reach the instance metadata service (no instance-role credentials)
#   - a sudo rule letting `agent` run only status.sh and deploy-main.sh, as ec2-user
#   - Claude Code and Python 3.11 for `agent`
#   - a GitHub Actions self-hosted runner, labelled `trademind`, running as `agent`
set -euo pipefail

AGENT_USER=agent
REPO_URL="${REPO_URL:-https://github.com/Shiv53336/Object_de}"
RUNNER_NAME="${RUNNER_NAME:-trademind-box}"
APP_DIR=/opt/trademind/trademind
HERE="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="/home/$AGENT_USER"
RUNNER_DIR="$HOME_DIR/actions-runner"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo RUNNER_TOKEN=... bash $0" >&2
  exit 1
fi

echo "== repository must be private"
# A self-hosted runner on a public repository lets a fork's pull request run code on this machine
# (GitHub's own guidance). An unauthenticated API call succeeds only for public repositories.
slug="${REPO_URL#https://github.com/}"
if curl -fsS -o /dev/null "https://api.github.com/repos/${slug}"; then
  echo "REFUSING: ${slug} is public. Make it private first (Settings > General > Danger Zone)." >&2
  exit 1
fi

echo "== packages"
dnf install -y -q git tar gzip libicu python3.11 python3.11-pip iptables-nft
if ! command -v gh >/dev/null; then
  curl -fsSL https://cli.github.com/packages/rpm/gh-cli.repo -o /etc/yum.repos.d/gh-cli.repo
  dnf install -y -q gh
fi

echo "== agent user"
id "$AGENT_USER" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$AGENT_USER"
if id -nG "$AGENT_USER" | tr ' ' '\n' | grep -qx docker; then
  gpasswd -d "$AGENT_USER" docker   # docker group membership is root-equivalent
fi
sudo -u "$AGENT_USER" mkdir -p "$HOME_DIR/tm-data"

echo "== production secrets: owner-only"
[ -f "$APP_DIR/.env" ] && chown ec2-user:ec2-user "$APP_DIR/.env" && chmod 600 "$APP_DIR/.env"
# The app container runs as uid 1000, the same uid as ec2-user, so it keeps access.
[ -d "$APP_DIR/data" ] && chmod 700 "$APP_DIR/data"
# The production clone's remote URL holds a GitHub token.
[ -f /opt/trademind/.git/config ] && chmod 600 /opt/trademind/.git/config

echo "== block instance metadata for $AGENT_USER"
install -m 644 "$HERE/trademind-agent-imds.service" /etc/systemd/system/trademind-agent-imds.service
systemctl daemon-reload
systemctl enable --now trademind-agent-imds.service
systemctl restart trademind-agent-imds.service
if sudo -u "$AGENT_USER" curl -s -m 3 -o /dev/null http://169.254.169.254/; then
  echo "FAILED: $AGENT_USER can still reach the metadata service" >&2
  exit 1
fi

echo "== sudo rule"
install -m 440 -o root -g root "$HERE/sudoers" /etc/sudoers.d/trademind-agent
visudo -cf /etc/sudoers.d/trademind-agent

echo "== Claude Code"
if [ ! -x "$HOME_DIR/.local/bin/claude" ]; then
  sudo -iu "$AGENT_USER" bash -c 'curl -fsSL https://claude.ai/install.sh | bash'
fi
sudo -iu "$AGENT_USER" "$HOME_DIR/.local/bin/claude" --version

echo "== GitHub Actions runner"
if [ ! -f "$RUNNER_DIR/.runner" ]; then
  : "${RUNNER_TOKEN:?set RUNNER_TOKEN (repo Settings > Actions > Runners > New self-hosted runner)}"
  version=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"].lstrip("v"))')
  curl -fsSL -o /tmp/actions-runner.tgz \
    "https://github.com/actions/runner/releases/download/v${version}/actions-runner-linux-arm64-${version}.tar.gz"
  sudo -u "$AGENT_USER" mkdir -p "$RUNNER_DIR"
  sudo -u "$AGENT_USER" tar xzf /tmp/actions-runner.tgz -C "$RUNNER_DIR"
  rm -f /tmp/actions-runner.tgz
  sudo -u "$AGENT_USER" bash -c "cd '$RUNNER_DIR' && ./config.sh --unattended --replace \
    --url '$REPO_URL' --token '$RUNNER_TOKEN' --name '$RUNNER_NAME' --labels trademind"
  (cd "$RUNNER_DIR" && ./svc.sh install "$AGENT_USER" && ./svc.sh start)
else
  echo "runner already configured; (re)starting it"
  (cd "$RUNNER_DIR" && ./svc.sh start || true)
fi

cat <<EOF

Done. Remaining one-time steps (docs/AGENT.md):
  1. terraform apply, then put the agent_role_arn output into the repository variable
     TRADEMIND_AGENT_ROLE_ARN (Settings > Secrets and variables > Actions > Variables).
  2. Settings > Actions > General > Workflow permissions: tick
     "Allow GitHub Actions to create and approve pull requests".
  3. In the Bedrock console (ap-south-1), open Model catalog and enable the Anthropic models once.
  4. Test: Actions > trademind-agent > Run workflow, mode=status.
EOF
