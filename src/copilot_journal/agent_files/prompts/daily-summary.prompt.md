---
description: "Generate a structured end-of-day journal entry by gathering git commits, AI session data, and memory notes. Use when you want a comprehensive daily summary."
mode: "agent"
---

# Daily Journal Summary

Generate a structured daily journal entry by gathering context from today's work.

## 1. Gather Context

- Check git log for today's commits: `git log --since="00:00" --oneline`
- Check `.ai_sessions/sessions.json` for today's sessions (if it exists)
- Review any session memory notes from `/memories/session/` (if it exists)
- Read today's existing journal file (if it exists) for any real-time entries already captured

## 2. Create/Update Daily Note

- Path: `{{JOURNAL_PATH}}/daily.{{YYYY}}.{{MM}}.{{DD}}.md`
- If file exists, update it (preserve any existing real-time entries under a "## Decision Log" section)
- If not, create it

## 3. Note Format

Use the developer's local time for all timestamps, not UTC. Do NOT duplicate the title — one H1 at the top only.

```markdown
---
id: daily.{{YYYY}}.{{MM}}.{{DD}}
title: Journal - {{Month DD, YYYY}}
created: {{local timestamp}}
updated: {{local timestamp}}
---

# Journal - {{Month DD, YYYY}}

## Summary
Brief 2-3 sentence overview of the day's work.

## Work Completed
- Bullet list of major accomplishments
- Reference specific files changed: [file.py](../src/path/file.py)
- Note any issues resolved or features added

## Commits
- List today's commits with short descriptions

## AI Sessions
- List session names and outcomes from today

## Decision Log
- (Preserve any real-time journal entries captured during the day)

## Notes
Any additional context, blockers, or thoughts for tomorrow.

## Next Steps
- What to pick up next session
```

## 4. Behavior

- Be concise but complete
- Use wiki links to previous days where appropriate: `[[daily.{{YYYY}}.{{MM}}.{{DD-1}}]]`
- Link to related documentation when relevant
- Include code snippets only if they illustrate key changes
- Track time estimates vs actual work where available from AI session data
