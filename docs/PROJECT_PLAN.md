# Project Plan — copilot-journal

This is a **historical record** of what was actually built, when, and why. For the philosophy and design intent behind this project, see [🧭 Intent](../README.md#-intent) in the README.

Current state: **v0.3.1** — 57 tests, zero runtime dependencies.

---

## Phase 1: Foundation (2026-02-17 → 2026-02-18)

**Goal:** Build a working installer that puts journaling instructions where Copilot can find them — local and global.

Established the core installer with Protocol-based dependency injection, template variable substitution, and both local (`.github/`) and global (VS Code User dir) install paths.

**Key decisions:**

- Protocol-based DI from day one — `FileSystemProtocol` / `EnvironmentProtocol` for testability without mocks
- Agent files bundled as package data, copied on install — not generated
- `{{JOURNAL_PATH}}` template variable for per-project customization
- Local and global install as separate code paths (not a flag on a shared path)

**Risk posture:** Low — single developer, no users. Move fast, get the installer working.

---

## Phase 2: Quality & Polish (2026-02-20)

**Goal:** Fix bugs found in real usage, establish project conventions, and document architecture thoroughly enough that an AI can work on the codebase without handholding.

Comprehensive code review uncovered 3 critical bugs (Insiders indexing, journal path mismatch, template drift). Created architecture documentation and project conventions. Removed AI-generated timestamps from journal format.

**Key decisions:**

- Explicit `"Code-Insiders"` string over fragile list indexing
- `docs/journal` over `docs/vault` — self-documenting beats Dendron jargon
- Static repo copies of instruction files — Copilot needs them without running the installer
- No AI timestamps — git history is the authoritative timeline
- Over-document for AI context windows (architecture README with invariants, Mermaid diagrams, AI-accessibility map)

**Design discussions (journal):**

- [2026-02-20](journal/daily.journal.2026.02.20.md) — Dendron config sync (rejected hardcoded YAML), project conventions placement (rejected README/CONTRIBUTING.md), 3 bug fixes with rejected alternatives, utils consolidation (rejected premature merge), timestamp removal (rejected guard-based approach)

**Risk posture:** Medium — preparing for public release. Architecture doc and conventions exist so future contributors (human or AI) don't introduce regressions. 57 tests, 70 passing after fixes.

---

## Version History

| Version | Date | Highlights |
| ------- | ---- | ---------- |
| v0.1.0 | 2026-02-17 | Initial installer — local + global, template vars |
| v0.2.0 | 2026-02-18 | Interactive journal path prompt, dry-run, logging |
| v0.3.0 | 2026-02-20 | Bug fixes, architecture docs, project conventions |
| **v0.3.1** | **Current** | **57 tests, zero dependencies** |

---

## Roadmap

| Item | Description | Status |
| ---- | ----------- | ------ |
| OpenClaw skill | Skill definition at `skill/copilot-journal/` | ✅ Done |
| Dendron vault setup prompt | One-command vault initialization | ✅ Done |
| Pre-commit hook | Auto-journal on commit (capture reasoning before it's lost) | Future |
| Multi-vault support | Multiple journal directories per project | Future |
| Journal search/index | Find past decisions by keyword | Future |
