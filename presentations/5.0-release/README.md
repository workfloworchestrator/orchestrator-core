# orchestrator-core 5.0 release deck

A ~15-minute operator-focused walkthrough of what changed in orchestrator-core
5.0, weighted toward breaking changes and major new features.

## Build

```bash
./build.sh
```

Produces `deck.pptx`. Open it in PowerPoint (or Keynote / LibreOffice) and
polish styling as needed. Speaker notes live in `::: notes` blocks in the
markdown and become PowerPoint speaker notes after conversion.

To apply a corporate template, drop a `.pptx` template alongside as
`reference.pptx` and uncomment the `--reference-doc=reference.pptx` line in
`build.sh`.

## Source map

Every claim in the deck traces back to a file in the repo:

| Slide                          | Source                                                                                          |
|--------------------------------|-------------------------------------------------------------------------------------------------|
| Prerequisites (4.7 / 4.8)      | `docs/guides/upgrading/4.7.md`, `docs/guides/upgrading/4.8.md`                                  |
| Breaking #1 (namespace)        | `docs/guides/upgrading/5.0.md` §1; motivation: `docs/architecture/extensibility/packaging.md`   |
| Breaking #2 (scheduled tasks)  | `docs/guides/upgrading/5.0.md` §1 (scheduled tasks warning); migration `cab8b6a0ac92`           |
| Breaking #3 (psycopg3)         | `docs/guides/upgrading/5.0.md` §11                                                              |
| Breaking #4 (secret URIs)      | `docs/guides/upgrading/5.0.md` §3                                                                |
| Breaking #5–8 (forms/GraphQL)  | `docs/guides/upgrading/5.0.md` §4 (pydantic-forms), §7 (Strawberry)                              |
| Breaking #9–12 (auth, misc)    | `docs/guides/upgrading/5.0.md` §9, §10, §5, §6                                                   |
| LLM search default             | `docs/guides/upgrading/5.0.md` §8; migration `262744958e0c`                                     |
| MCP server                     | PRs #1483 and #1620                                                                              |
| `register_table()`             | `docs/guides/upgrading/5.0.md` §12                                                              |

When the upgrade guide is updated, refresh this deck by re-reading the
referenced sections and amending matching slides.
