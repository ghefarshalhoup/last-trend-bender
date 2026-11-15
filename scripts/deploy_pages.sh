#!/usr/bin/env bash
# Build the static site and publish it to the gh-pages branch (GitHub Pages).
#   bash scripts/deploy_pages.sh
# Site: https://ghefarshalhoup.github.io/war-environment-tracker/#/atlas
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
npm run build:pages
cd "$ROOT"
python3 scripts/export_static_api.py frontend/dist
touch frontend/dist/.nojekyll
SHA="$(git rev-parse --short HEAD)"
TMP="$(mktemp -d)"
cp -r frontend/dist/. "$TMP/"
cd "$TMP"
git init -q -b gh-pages
git add -A
git -c user.name="deploy" -c user.email="deploy@users.noreply.github.com" commit -q -m "Static site from $SHA"
git push -q -f "$(git -C "$ROOT" remote get-url origin)" gh-pages
echo "Published $SHA to gh-pages. GitHub Pages updates within a few minutes."
