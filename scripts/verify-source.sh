#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if grep -R "stream_urls_" -n src include; then
  echo "ERREUR: ancienne variable stream_urls_ détectée" >&2
  exit 1
fi
count=$(grep -R "^void Application::initialize_players" -n src/Application.cpp | wc -l)
if [ "$count" -ne 1 ]; then
  echo "ERREUR: initialize_players doit être défini exactement une fois" >&2
  exit 1
fi
echo "Sources PiDecoder v0.4.1 cohérentes."
