#!/bin/bash
#
# Regenerate the Sparkle appcast from the built .dmg(s) in macos/dist/.
#
# Run this AFTER build_release.sh + notarize + staple, once you know the GitHub Release
# tag the .dmg will be uploaded under:
#
#   ./scripts/make_appcast.sh <github-release-tag>
#   e.g.  ./scripts/make_appcast.sh macos-v0.1.1
#
# Writes macos/appcast.xml (the file SUFeedURL points at). The EdDSA private key is read
# from your login Keychain (created earlier by `generate_keys`) — you may get one Keychain
# access prompt; allow it. Afterwards: verify the URLs in appcast.xml, then commit + push it.
#
set -euo pipefail
cd "$(dirname "$0")/.."          # -> macos/

TAG="${1:-}"
if [ -z "$TAG" ]; then
  echo "usage: $0 <github-release-tag>    e.g.  $0 macos-v0.1.1"
  exit 1
fi

REPO="EvanYifanYang/connectonion-studio"
PREFIX="https://github.com/$REPO/releases/download/$TAG/"
TOOLS=".sparkle-tools/bin"
DIST="dist"

[ -x "$TOOLS/generate_appcast" ] || { echo "Sparkle tools missing at $TOOLS/ — re-download them."; exit 1; }
ls "$DIST"/*.dmg >/dev/null 2>&1  || { echo "no .dmg in $DIST/ — run build_release.sh (+ notarize/staple) first."; exit 1; }

# generate_appcast treats EVERY archive in the folder as an update, and dist/ also holds build
# byproducts (python*.tar.gz). Isolate just the .dmg(s) in a clean staging dir so those don't
# get picked up ("Duplicate update archives" error otherwise).
STAGE="$DIST/appcast-stage"
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp "$DIST"/*.dmg "$STAGE"/
# carry the existing feed in so older, already-signed entries are preserved (not dropped).
[ -f appcast.xml ] && cp appcast.xml "$STAGE/appcast.xml"

echo "generating appcast for $STAGE/*.dmg"
echo "  download-url-prefix: $PREFIX"
"$TOOLS/generate_appcast" "$STAGE" \
    --download-url-prefix "$PREFIX" \
    --link "https://github.com/$REPO"

mv "$STAGE/appcast.xml" appcast.xml
rm -rf "$STAGE"

echo ""
echo "DONE -> macos/appcast.xml"
echo "Next:"
echo "  1. eyeball the <enclosure url> lines in macos/appcast.xml (esp. if you have >1 version / tag)"
echo "  2. upload $DIST/*.dmg to the GitHub Release tagged '$TAG'"
echo "  3. git add macos/appcast.xml && git commit && git push   (SUFeedURL serves it via raw.githubusercontent)"
