---
name: copilot-journal
description: Journal design decisions, reasoning, and tradeoffs while coding. Triggers: "journal that", "log this", "why did we do this?", or after significant decisions/failed attempts/session wrap-up.
---

# Copilot Journal — Decision Journaling

Git captures **what**. The journal captures **why**.

## Where to Write

Daily files `YYYY-MM-DD.md` in the project's journal directory. Path configured via `copilot-journal --journal-path <path>` (default: `docs/journal/`). Check `journaling.instructions.md` for the configured path. Create the directory if missing.

## How to Write

Read today's file first. Append only — never overwrite. Create if missing.

## Entry Format

```markdown
## 10:45 AM
Chose X over Y because Z. Revisit in Q3.
```

## Capture

Decisions/reasoning, tradeoffs, failed attempts, open questions, end-of-session context.

## Skip

Code changes, status updates, formatting/style choices.

## Triggers

- **"journal that"** — capture reasoning from current conversation
- **"log this"** — quick capture
- **"why did we do this?"** — write a decision record

## Proactive

After significant decisions or task completion, offer once: "Want me to log why we went this direction?"

## Install

pip: [mgrandau/copilot-journal](https://github.com/mgrandau/copilot-journal)
