# Contributing

The workflow orchestrator projects welcomes any contributions from any party. If you are interested in contributing
or have questions about the project please contact the board: workfloworchestrator.board@commonsconservancy.org or feel
free to raise an issue in the project. We will strive to reply to your enquiry A.S.A.P.

## Documentation

We use [**MKDOCS**](https://www.mkdocs.org) as a documentation tool. Please create a PR if you have any additions or contributions to make. All docs can be written in MD or html. Full guidelines on how to set this up can be found [here](development.md).

## Branch naming

Use the pattern `<type>/<issue-number>-<short-slug>`:

- `feature/` — new functionality
- `fix/` — bug fixes
- `chore/` — maintenance, tooling, dependency pins
- `docs/` — documentation-only changes
- `refactor/` — structural changes with no behaviour change

Keep the slug lowercase and hyphen-separated. Examples:

```
feature/1234-run-predicate
fix/57-subscription-count-hyphen
docs/42-contributing-commit-guide
refactor/4725-isinstance-to-match-case
```

## Commit messages

Write commit messages in the **imperative mood**, sentence case, with no trailing period. Aim to keep the subject line under 72 characters.

```
# Good
Add run_predicate to workflow decorator
Fix subscription count for products with hyphen in name
Refactor isinstance chains to match/case structural pattern matching
Remove starlette version pin

# Avoid
added run predicate          # past tense
fix                          # too vague
Lets not add superpowers     # not imperative, no context
```

If the change needs more explanation, add a blank line after the subject and write a body:

```
Fix scheduler using the same SQLAlchemy session

The scheduler was reusing a single session across concurrent tasks,
causing state bleed. Each task now gets its own session.
```

**Issue references** go in the PR description, not the subject line. GitHub will close the issue automatically when the PR merges if you write `Fixes #123` or `Closes #123` in the PR body.

The `(#PR-number)` suffix is appended automatically by GitHub on squash merge — do not add it by hand.

## Pre-commit hooks

We use pre-commit hooks to ensure that the code is formatted correctly and that the tests pass.
To install the pre-commit hooks, run the following command:

```shell
uv run pre-commit install
```

To run the pre-commit hooks manually, run the following command:

```shell
uv run pre-commit run --all-files
```

## Updating AI context (CLAUDE.md)

The repository includes a `CLAUDE.md` file at its root. This file is read by AI coding assistants (such as Claude Code) to understand the project's conventions without repeated explanation. It covers build commands, code style rules, key directory layout, test markers, and commit message guidance.

The PR checklist asks you to keep it current. Update (or have Claude update) `CLAUDE.md` when you:

- Add or rename a CLI command or common `uv run` invocation
- Change a code style rule (line length, import style, docstring convention, etc.)
- Add a new top-level package or significantly restructure the directory layout
- Add, rename, or remove a pytest marker
- Change the Python version range or package manager tooling

You do not need to update it for normal feature work, bug fixes, or dependency bumps.

## Orchestrator release

The `orchestrator-core` has no release schedule but is actively used and maintained by the workflow orchestrator group.
Creating a new release is done by the developers of the project and the procedure is as follows.

### Release candidates

When creating new features they can be released in so-called `pre-releases` on github.
Depending on the feature type the developer will need to run `bumpversion (major|minor|patch)` and then `bumpversion build --allow-dirty` to create a new release candidate.
This command will update the `.bumpversion.cfg` and the `orchestrator/__init__.py` files.

The next step would be to "Create a new release" -> "Fill in the tag and check the box, create tag upon release" and
use the checkbox "pre-release."

The code will be pushed to pypi.

### Stable releases

Stable releases follow the same procedure as described above and can be either created from a release candidate by removing the `-rc` string from the `.bumpversion.cfg` and the `orchestrator/__init__.py` files.
After that a new release can be created and the `Autogenerate changelog` option may be used.
