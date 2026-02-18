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

## Quick Commands

Use these phrases naturally in your Copilot chat:

| Command | What happens |
|---------|-------------|
| `"journal that"` | Captures reasoning from current conversation |
| `"log this"` | Quick capture of what you just discussed |
| `"why did we do this?"` | Writes a decision record |

## Install

```bash
pip install copilot-journal
```

### Local (per-repo, default)

```bash
cd your-project
copilot-journal
```

Installs to `.github/instructions/journaling.instructions.md`

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

## License

MIT
