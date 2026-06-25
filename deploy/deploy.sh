#!/usr/bin/env bash
# Deploy pi-dashboard from a dev machine to the Pi over SSH (no rsync needed).
# Run from a Unix-ish shell (Git Bash/WSL on Windows, or macOS/Linux):
#   deploy/deploy.sh pi@raspberrypi.local [remote_dir]
# Default remote_dir is ~/pi-dashboard on the Pi.
set -euo pipefail

TARGET="${1:?Usage: deploy.sh user@host [remote_dir]}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REMOTE_HOME="$(ssh "$TARGET" 'echo $HOME')"
REMOTE_DIR="${2:-$REMOTE_HOME/pi-dashboard}"

echo ">> deploying $SRC -> $TARGET:$REMOTE_DIR"
ssh "$TARGET" "mkdir -p '$REMOTE_DIR'"

# Stream the project (minus venv/data/git/secrets/screenshots) via tar over ssh.
tar -C "$SRC" \
  --exclude=.venv --exclude=data --exclude=.git \
  --exclude='deploy/secrets.env' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='dashboard.png' \
  -czf - . | ssh "$TARGET" "tar -C '$REMOTE_DIR' -xzf -"

# Normalize line endings in case files came from Windows, then install.
echo ">> running remote install"
ssh "$TARGET" "cd '$REMOTE_DIR' && sed -i 's/\r\$//' deploy/install.sh deploy/kiosk/pidash-kiosk.sh 2>/dev/null || true; bash deploy/install.sh"
