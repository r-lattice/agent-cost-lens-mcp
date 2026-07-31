#!/usr/bin/env bash
# Print the release-notes path for <tag>, or refuse. Run from the repo root.
set -euo pipefail

tag="${1:?usage: release-guard.sh <tag>}"
expected="v$(sed -n 's/^## \[\([0-9][0-9.]*\)\].*/\1/p' CHANGELOG.md | head -1)"

if [ "$tag" != "$expected" ]; then
  echo "refusing: tag $tag is not this snapshot's product version $expected." >&2
  echo "releases/ and CHANGELOG.md are versioned by the product; the pip package" >&2
  echo "has its own version stream. Tagging a package version here would publish" >&2
  echo "a different release's notes. Tag $expected instead." >&2
  exit 1
fi

notes="releases/$tag.md"
if [ ! -f "$notes" ]; then
  echo "refusing: no $notes in this snapshot" >&2
  exit 1
fi

echo "$notes"
