#!/bin/bash
set -e

# ── Read & bump patch version ─────────────────────────────────────────────────
CURRENT=$(cat VERSION)
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"
NEXT="$MAJOR.$MINOR.$((PATCH + 1))"
TAG="v$NEXT"

echo "Releasing: $CURRENT → $NEXT"

# ── Bump version ──────────────────────────────────────────────────────────────
echo "$NEXT" > VERSION

# ── Generate CHANGELOG with the new tag (suppress pre-commit hook) ────────────
touch .git/hooks/.cliff-running
git-cliff --config cliff.toml --tag "$TAG" -o CHANGELOG.md
rm -f .git/hooks/.cliff-running

# ── Stage everything & commit ─────────────────────────────────────────────────
git add -A
git commit -m "chore: release $TAG"

# ── Tag ───────────────────────────────────────────────────────────────────────
git tag "$TAG"

# ── Push branch + tag ─────────────────────────────────────────────────────────
git push origin HEAD
git push origin "$TAG"

# ── Build Windows zip asset ───────────────────────────────────────────────────
ZIP_NAME="voice-input-windows-$NEXT.zip"
zip -r "$ZIP_NAME" src/ assets/ requirements-windows.txt VERSION voice-input-config.json setup.py install.bat \
  -x "src/__pycache__/*" -x "src/*.pyc" -x "*/.DS_Store"

# ── GitHub release notes ──────────────────────────────────────────────────────
CHANGELOG_SECTION=$(git-cliff --config cliff.toml --latest --strip all 2>/dev/null || echo "")

NOTES="## Installation

**Windows** — download \`voice-input-windows-$NEXT.zip\`, extract anywhere, double-click \`install.bat\`

**macOS** — download \`install.command\`, double-click in Finder

## Changes

$CHANGELOG_SECTION"

gh release create "$TAG" \
  --title "Voice Input $TAG" \
  --notes "$NOTES" \
  "$ZIP_NAME"

rm -f "$ZIP_NAME"

echo ""
echo "✅ Released $TAG and published to GitHub!"
