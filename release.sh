#!/bin/bash
set -e

# ── Read & bump patch version ─────────────────────────────────────────────────
CURRENT=$(cat VERSION)
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"
NEXT="$MAJOR.$MINOR.$((PATCH + 1))"
TAG="v$NEXT"

echo "Releasing: $CURRENT → $NEXT"

# ── Check working tree is clean (except VERSION/CHANGELOG) ───────────────────
DIRTY=$(git status --porcelain | grep -v "^??" | grep -v "VERSION" | grep -v "CHANGELOG.md" || true)
if [ -n "$DIRTY" ]; then
  echo "❌ Working tree has uncommitted changes:"
  echo "$DIRTY"
  echo "Commit or stash them before releasing."
  exit 1
fi

# ── Bump version ──────────────────────────────────────────────────────────────
echo "$NEXT" > VERSION

# ── Generate CHANGELOG with the new tag (suppress pre-commit hook) ────────────
touch .git/hooks/.cliff-running
git-cliff --config cliff.toml --tag "$TAG" -o CHANGELOG.md
rm -f .git/hooks/.cliff-running

# ── Stage & commit ────────────────────────────────────────────────────────────
git add VERSION CHANGELOG.md
git commit -m "chore: release $TAG"

# ── Tag ───────────────────────────────────────────────────────────────────────
git tag "$TAG"

# ── Push branch + tag ─────────────────────────────────────────────────────────
git push origin HEAD
git push origin "$TAG"

# ── GitHub release with notes from this version's CHANGELOG section ───────────
NOTES=$(git-cliff --config cliff.toml --unreleased --strip all --tag "$TAG" 2>/dev/null || echo "Release $TAG")
gh release create "$TAG" \
  --title "Release $TAG" \
  --notes "$NOTES"

echo ""
echo "✅ Released $TAG and published to GitHub!"
