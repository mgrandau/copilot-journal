---
applyTo: "**"
---

# Project Intent & Design

This project follows the [Human-AI Intent Transfer Principles](https://mgrandau.medium.com/human-ai-intent-transfer-principles-b6e7404e3d26?source=friends_link&sk=858917bd3f4a686974ed6b6c9c059ac8) — the journal IS the intent transfer mechanism.

**Context chain (read in order when making design decisions):**

1. [🧭 Intent](../../README.md#-intent) — project philosophy: git captures what, journal captures why
2. [PROJECT_PLAN.md](../../docs/PROJECT_PLAN.md) — phase goals, risk posture, version history
3. [Journal entries](../../docs/journal/) — design alternatives explored and rejected, with rationale
4. [Architecture](../../src/copilot_journal/README.md) — component map, invariants, DI contracts, AI-accessibility map
5. Source code — the implementation

**Core design values (from rejection patterns in the journal):**

- **Zero runtime dependencies** — stdlib only, no pip installs needed beyond the package itself
- **Protocol-based DI** — testability without mocks, `FileSystemProtocol` / `EnvironmentProtocol`
- **Agent files are package-managed** — bundled templates, copied on install, not user-editable
- **Self-documenting defaults** — `docs/journal` not `docs/vault`, explicit strings not list indexing
- **Static repo copies** — `.github/instructions/` exists so Copilot works without running the installer
- **Git is the timeline** — no AI timestamps, `git log` and `git blame` are authoritative

When proposing new features or changes, check the journal for prior art — the alternative you're considering may have already been evaluated and rejected.

# GitHub CLI Quick Reference

Requires: `gh auth status` (authenticated).

## Project Conventions

| Action | Command |
| --- | --- |
| Bug | `gh issue create --label "bug"` |
| Feature | `gh issue create --label "enhancement"` |
| Start work | `gh issue edit N --add-label "in-progress" --add-assignee @me` |
| Submit fix | `gh pr create --title "Fix #N"` (auto-links issue) |
| Merge | `gh pr merge N --squash --delete-branch` |

## Release Process

### Version Badge

The README badge auto-updates from GitHub releases — no manual badge edits needed.

### Release Steps

1. Update version in `src/copilot_journal/__version__.py`
2. Commit changes: `git commit -am "release: bump version to X.X.X"`
3. Create and push tag: `git tag vX.X.X && git push origin vX.X.X`
4. Create GitHub release with **changelog notes** covering:
   - **Bug Fixes** — issues fixed with brief description
   - **Features** — new functionality added
   - **Documentation** — significant doc improvements
   - Link to full changelog comparison: `https://github.com/mgrandau/copilot-journal/compare/vPREV...vX.X.X`

### Changelog Requirements

- Every release **must** have human-written changelog notes — do not rely solely on `--generate-notes`
- Reference issue numbers (e.g., "Fixed #3: journal path mismatch")
- Keep notes concise but meaningful — someone reading them should understand what changed and why

### Notes

- Tags must match pattern `vX.X.X` (e.g., `v0.3.1`)
- `--generate-notes` auto-generates release notes from commits
- Badge updates within minutes of release creation

## PDM Scripts

| Script | Command | Purpose |
| --- | --- | --- |
| Lint | `pdm run lint` | Ruff check src + tests |
| Format | `pdm run format` | Ruff format src + tests |
| Security | `pdm run security` | Bandit scan on src |
| Test | `pdm run test` | pytest verbose |
| Coverage | `pdm run test-cov` | pytest with branch coverage |
| Types | `pdm run typecheck` | mypy --strict on src |
| All | `pdm run check-all` | lint + typecheck + security + test-cov |

Run `pdm run check-all` before committing.

## Tips

- `--web`: open in browser
- `--json field1,field2 --jq '...'`: scriptable output
- `gh <cmd> --help`: full options

## Markdown

All markdown files must pass linting. Fix errors before committing.

**Always**: blank line before/after headings, tables, lists, code blocks. Specify language on fenced blocks.

**Tables**: spaces around pipes in separator row (`| --- |` not `|---|`).

## Documentation

Over-document for AI context windows. All public functions, Protocol methods, test fakes, and thin delegates require full docstrings. Docstrings are context — they help Copilot understand intent, business logic, and relationships between components.

## Git

Commits: `feat:|fix:|docs:|refactor:|test:|chore:` + description. Branches: `main`, `feature/<x>`, `fix/<x>`.
