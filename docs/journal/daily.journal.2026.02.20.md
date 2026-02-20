---
id: e51b44b7-d82d-4911-b9bd-0ba8b1fd887a
title: "February 20, 2026"
desc: ""
updated: 1771616668157
created: 1771616668157
---

# Journal - February 20, 2026

First entry. Dendron vault initialized for project journaling.

## 1:58 PM

Synced root `dendron.yml` with the full config from `docs/journal/dendron.yml`. The root config was missing most sections — dev, commands, scratch, task, graph, workspace flags, preview, and publishing settings. Also removed `enablePersistentHistory` which the Dendron schema flagged as invalid.

Updated `setup-dendron-vault.prompt.md` to stop hardcoding the YAML config. Instead it now references `docs/journal/dendron.yml` as the canonical source and requires zero validation errors. Went this way because hardcoded config in prompts drifts silently — the root `dendron.yml` was already out of date from the prompt's own template. Pointing at the live file means the setup prompt stays correct as Dendron evolves, and the validation step catches invalid properties before they ship.

## 2:45 PM

Created `.github/instructions/project.instructions.md` — modeled after the one in `docscope-mcp`. Covers release workflow (edit `__version__.py`, tag, push, `gh release create`), PDM scripts table, gh CLI conventions, markdown rules, and git commit prefixes.

Went this way because the docscope-mcp project already had this and it was useful there for keeping Copilot aligned on project conventions. The release process in particular needs to be discoverable — version lives in `src/copilot_journal/__version__.py`, and the tag+release flow is easy to get wrong without a reference. PDM scripts table gives Copilot (and contributors) a single place to see all available quality checks without reading `pyproject.toml`.
