# copilot-journal

Install GitHub Copilot instructions that enable automatic journaling of design decisions, reasoning, and context as you code.

## What It Does

After installation, GitHub Copilot will automatically:

- **Capture design decisions** — why you chose approach X over Y
- **Log tradeoffs** — what was considered and rejected
- **Record failed attempts** — what didn't work and why
- **Note open questions** — things to revisit later
- **Summarize sessions** — where you left off and what's next

## What It Doesn't Do

- Duplicate what git already captures (file changes, diffs)
- Write status updates ("I did X")
- Add friction to your workflow

## Two Modes

### Real-time capture (always on)
The instruction file runs passively during every Copilot interaction. Use trigger phrases to capture reasoning as it happens:

| Command | What happens |
|---------|-------------|
| `"journal that"` | Captures reasoning from current conversation |
| `"log this"` | Quick capture of what you just discussed |
| `"why did we do this?"` | Writes a decision record |

### End-of-day summary (on demand)
The prompt file generates a structured daily summary when you invoke it. It automatically gathers git commits, AI session data, and memory notes into a formatted journal entry.

Invoke it in Copilot chat by selecting the `daily-summary` prompt, or just say "summarize today".

## Install

```bash
pip install copilot-journal
```

### Local (per-repo, default)

```bash
cd your-project
copilot-journal
```

Installs to `.github/`:
- `instructions/journaling.instructions.md` — always-on, captures decisions as you work
- `prompts/daily-summary.prompt.md` — on-demand end-of-day summary

### Global (all repos)

```bash
copilot-journal --global
```

Installs to your VS Code User `prompts/` directory.

### Options

```bash
copilot-journal --journal-path my/journal  # Custom journal location
copilot-journal --global --insiders        # VS Code Insiders
copilot-journal --dry-run                  # Preview without copying
copilot-journal --log-level DEBUG          # Verbose output
```

When run interactively, the installer will prompt you for the journal path:

```
📓 Where should journal entries be stored? [docs/vault]: 
```

Press Enter to accept the default (`docs/vault`) or type a custom path.

## Journal Setup

After installing the instructions, create your journal directory in your project:

```bash
mkdir -p docs/vault    # or whatever path you specified during install
```

Copilot will write daily entries like `docs/vault/2026-02-18.md` with timestamped entries capturing your reasoning as you work.

## Philosophy

Your git log captures **what** changed. Your journal captures **why**.

Six months from now, when someone asks "why did you do it this way?" — you'll have the answer.

## OpenClaw Skill

This repo also includes an [OpenClaw](https://github.com/openclaw/openclaw) skill at `skill/copilot-journal/`. To install it, copy the skill folder to your OpenClaw skills directory:

```bash
cp -r skill/copilot-journal /path/to/openclaw/skills/
```

This gives OpenClaw agents the same journaling workflow — capture decisions, reasoning, and context automatically.

## 💬 Community

💬 [Join the Discord community](https://discord.gg/2KqjHvh5)

## License

MIT
