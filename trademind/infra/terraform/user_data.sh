#!/bin/bash
# First boot: Docker, the Compose plugin, git, IST time zone, and the app folder.
set -euxo pipefail
timedatectl set-timezone Asia/Kolkata
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-aarch64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
mkdir -p /opt/trademind
chown ec2-user:ec2-user /opt/trademind
