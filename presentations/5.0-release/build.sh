#!/usr/bin/env bash
# Build deck.pptx from deck.md using pandoc.
# Drop a corporate template into reference.pptx and uncomment the line below
# to apply your house style.

set -euo pipefail

cd "$(dirname "$0")"

pandoc deck.md \
    --slide-level=1 \
    -o deck.pptx
#   --reference-doc=reference.pptx

echo "Wrote $(pwd)/deck.pptx"
