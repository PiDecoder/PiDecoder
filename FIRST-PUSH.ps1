$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/PiDecoder/PiDecoder.git"

git init
git branch -M main
git remote remove origin 2>$null
git remote add origin $RepoUrl

git add .
git commit -m "Initial public release candidate v0.9.9.4"
git push -u origin main
