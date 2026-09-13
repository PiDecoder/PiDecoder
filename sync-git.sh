#!/usr/bin/env bash
# Petite macro : add + commit + push en une commande, avec confirmation
# avant d'envoyer quoi que ce soit. Fonctionne dans Git Bash et MobaXterm.
#
# Usage :
#   ./sync-git.sh "message de commit"
#   ./sync-git.sh            (le message est demandé si absent)

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Garde-fou contre le faux "tout est modifié" (bit exécutable qui saute
# sur les montages OneDrive/réseau). Sans ça, git add -A pourrait ajouter
# des dizaines de fichiers non voulus.
if [[ "$(git config --get core.fileMode || echo true)" != "false" ]]; then
    git config core.fileMode false
    echo "core.fileMode désactivé pour ce dépôt (évite les faux positifs de permissions)."
fi

if [[ -z "$(git status --porcelain)" ]]; then
    echo "Rien à envoyer, le dépôt est propre."
    exit 0
fi

echo "== Changements détectés =="
git status --short
echo

MESSAGE="${1:-}"
if [[ -z "$MESSAGE" ]]; then
    read -rp "Message de commit : " MESSAGE
fi

if [[ -z "$MESSAGE" ]]; then
    echo "Message vide, annulation." >&2
    exit 1
fi

git add -A

echo
echo "== Fichiers qui vont être commités =="
git status --short
echo

read -rp "Confirmer le commit et le push ci-dessus ? [o/N] " CONFIRM
if [[ "$CONFIRM" != "o" && "$CONFIRM" != "O" ]]; then
    echo "Annulé, fichiers désindexés."
    git reset >/dev/null
    exit 1
fi

git commit -m "$MESSAGE"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    git push
else
    git push -u origin "$BRANCH"
fi

echo
echo "Envoyé sur origin/$BRANCH."
