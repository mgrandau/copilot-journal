---
applyTo: "**"
---

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

## Release

```bash
# 1. Update version
# Edit src/copilot_journal/__version__.py

# 2. Commit, tag, push, release
git commit -am "Bump to X.X.X" && git tag vX.X.X && git push origin vX.X.X
gh release create vX.X.X --title "vX.X.X" --generate-notes
```

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
