## Journal

This project includes a journal vault at `{{JOURNAL_PATH}}` for capturing design decisions,
reasoning, and context as you work.

### Automatic Journaling

As you work with Copilot in this project, journaling is built into the workflow:

- **After significant decisions**, Copilot will write a brief journal entry explaining
  WHY the approach was chosen over alternatives
- **After completing a task**, Copilot may ask: "Want me to log why we went this
  direction?" — say yes to capture the reasoning
- **When you mention tradeoffs** or rejected approaches, those get captured too
- **Failed attempts** are logged — knowing what didn't work is as valuable as what did

### Quick Commands

Use these phrases naturally in your Copilot chat:

- **"journal that"** — Copilot captures the reasoning from the current conversation
- **"log this"** — quick capture of whatever you just discussed
- **"why did we do this?"** — Copilot writes a decision record to the journal

### Journal Format

Entries are daily files named `YYYY-MM-DD.md` in `{{JOURNAL_PATH}}`.

**Before writing:** Always read today's existing file first. Append new entries below existing ones. Never overwrite previous entries.

If no file exists for today, create one with a single H1 title. Do NOT duplicate the title — one `# Journal - Month DD, YYYY` at the top, that's it.

**Timestamps must use the developer's local time**, not UTC. Use 12-hour format with AM/PM.

Entry format — timestamp + thought, no ceremony:

```markdown
# Journal - February 18, 2026

## 3:45 PM
Chose approach X over Y because Z. Y would have required refactoring the
entire module, and the deadline doesn't allow for that. Revisit in Q3.

## 4:20 PM
Hit a wall with the async approach — race condition on concurrent writes.
Switched to synchronous queue. Slower but correct.
```

### What Gets Captured

- **Decisions and reasoning** — why this approach, not just what changed
- **Tradeoffs considered** — what was rejected and why
- **Failed attempts** — what didn't work and lessons learned
- **Open questions** — things to revisit later
- **End-of-session context** — where you left off, what's next

### What Doesn't Get Captured

- Code changes (git handles that)
- Status updates ("I did X" — the commit log shows that)
- Formatting or style choices (not worth journaling)
