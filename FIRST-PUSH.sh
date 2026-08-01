#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-https://github.com/PiDecoder/PiDecoder.git}"

git init
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"

git add .
git commit -m "Initial public release candidate v0.9.9.4"
git push -u origin main
