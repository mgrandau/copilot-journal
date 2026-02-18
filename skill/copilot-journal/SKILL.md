---
name: copilot-journal
description: Automatically journal design decisions, reasoning, tradeoffs, and context while working on code. Use when the user says "journal that", "log this", "why did we do this?", or asks to capture reasoning, decisions, or context. Also use after significant architectural decisions, failed attempts, or when wrapping up a coding session.
---

# Copilot Journal — Decision Journaling

## Where to Write

Write entries to the project's journal directory using daily files named `YYYY-MM-DD.md`. The journal path is configured during installation via `copilot-journal --journal-path <path>` (default: `docs/vault/`). Check the installed `journaling.instructions.md` for the configured path, or look for an existing journal directory in the project. Create the directory if it doesn't exist.

## How to Write

1. **Check for today's file first** — read the existing daily file (e.g., `2026-02-18.md`) before writing. Append new entries below existing ones.
2. Use daily files named `YYYY-MM-DD.md`
3. If no file exists for today, create one
4. Never overwrite existing entries — always append

## Entry Format

Timestamp + thought. No ceremony:

```markdown
## 10:45 AM
Chose approach X over Y because Z. Y would have required refactoring the
entire module, and the deadline doesn't allow for that. Revisit in Q3.
```

## What to Capture

- **Decisions and reasoning** — WHY this approach, not just what changed
- **Tradeoffs considered** — what was rejected and why
- **Failed attempts** — what didn't work and lessons learned
- **Open questions** — things to revisit later
- **End-of-session context** — where you left off, what's next

## What NOT to Capture

- Code changes (git handles that)
- Status updates ("I did X" — the commit log shows that)
- Formatting or style choices

## Trigger Phrases

- **"journal that"** — capture reasoning from the current conversation
- **"log this"** — quick capture of what was just discussed
- **"why did we do this?"** — write a decision record

## Proactive Journaling

After significant decisions or completing a task, offer: "Want me to log why we went this direction?" Keep it lightweight — one question, not a nag.

## Philosophy

Git captures **what** changed. The journal captures **why**. Six months from now, when someone asks "why did you do it this way?" — the journal has the answer.

## Background

The pip-installable version for GitHub Copilot in VS Code is at [mgrandau/copilot-journal](https://github.com/mgrandau/copilot-journal).
