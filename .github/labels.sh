#!/usr/bin/env bash
#
# Create or update the repository labels used by the release-notes generator
# (.github/release.yml) and the path-based labeler (.github/labeler.yml).
#
# Labels are namespaced:
#   kind/*  — the type of change (drives most changelog sections)
#   area/*  — the code area (only "Search / LLM" is its own section today)
#
# `gh label create --force` is idempotent: it creates the label, or updates its
# color/description if it already exists. Safe to run repeatedly.
#
# Usage:
#   .github/labels.sh                       # acts on the current repo
#   .github/labels.sh --repo owner/name     # extra args are forwarded to gh
#
# Requires the GitHub CLI (`gh auth login`).
set -euo pipefail

# name|color|description  (color is a 6-digit hex, no leading '#')
#
# One hue per namespace so this dedicated release-notes set reads as its own
# family and does not clash with the existing project-filter labels (bug,
# documentation, ...):
#   kind/*  -> blue    (0052cc)
#   area/*  -> purple  (5319e7)
#   exclusion marker -> grey (ededed)
labels=(
  "kind/feature|0052cc|New user-facing functionality"
  "kind/bug|0052cc|A confirmed bug fix"
  "kind/refactor|0052cc|Internal refactor with no behavior change"
  "kind/chore|0052cc|Housekeeping / internal change"
  "kind/documentation|0052cc|Documentation only"
  "kind/test|0052cc|Tests only"
  "kind/ci|0052cc|CI, GitHub Actions and workflow changes"
  "kind/build|0052cc|Build system, packaging and tooling"
  "kind/security|0052cc|Security fix or hardening"
  "kind/dependencies|0052cc|Dependency version updates"
  "area/search|5319e7|Search subsystem"
  "area/llm|5319e7|LLM / embeddings"
  "skip-changelog|ededed|Exclude this PR from the generated release notes"
)

for entry in "${labels[@]}"; do
  IFS='|' read -r name color description <<<"$entry"
  echo "Syncing label: ${name}"
  gh label create "$name" --color "$color" --description "$description" --force "$@"
done

echo "Done. ${#labels[@]} labels synced."
