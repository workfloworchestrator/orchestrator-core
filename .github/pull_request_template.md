## Summary
<!-- A summary of your changes -->

## Related Issues
Fixes # (issue number)

## Type of change
<!--
Set a label on this PR so it is categorized in the release notes. This is
required — the "Require a release-notes label" check fails without one.
kind/documentation, kind/test, kind/ci and kind/build are applied automatically,
but only when EVERY file you changed is of that kind (e.g. a tests-only PR gets
kind/test). area/search is applied when you touch orchestrator/core/search/.
A PR that changes other library code needs a type label set by hand, such as
kind/feature, kind/bug, kind/deprecation or kind/refactor.

A PR lands in only the FIRST matching release-notes section, and Breaking
Changes comes first — so a breaking feature is listed there rather than under
Features. That is intended: it is the section people read when upgrading.
-->
- [ ] I have set a `kind/*` label describing the change (e.g. `kind/feature`, `kind/bug`, `kind/refactor`), an `area/*` label, or `skip-changelog` if it should be left out of the notes.
- [ ] If this is a breaking change, I have set `kind/breaking`. Breaking changes belong in a **major** release and need an entry in [`docs/guides/upgrading/`](https://github.com/workfloworchestrator/orchestrator-core/tree/main/docs/guides/upgrading) describing what users must do.
- [ ] If this deprecates something users rely on (a public function, schema, API call or core behavior), I have set `kind/deprecation`, added an entry to [`docs/guides/upgrading/`](https://github.com/workfloworchestrator/orchestrator-core/tree/main/docs/guides/upgrading) describing what to use instead, and opened a follow-up issue to remove it in the next **major** release.

## Checklist
- [ ] I have updated relevant documentation.
- [ ] I have updated AI context (i.e., CLAUDE.md) as described in [CONTRIBUTING](https://github.com/workfloworchestrator/orchestrator-core/blob/main/docs/contributing/guidelines.md), if applicable.
- [ ] My code follows the style guidelines of this project as described in [CONTRIBUTING](https://github.com/workfloworchestrator/orchestrator-core/blob/main/docs/contributing/guidelines.md).
