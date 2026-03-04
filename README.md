# copilot-journal

Install GitHub Copilot instructions that enable automatic journaling of design decisions, reasoning, and context as you code.

## 🧭 Intent

Your git log captures **what** changed. Your journal captures **why.**

Most AI-assisted development loses context the moment the conversation ends. The code lands in a commit, but the reasoning — why you chose approach X over Y, what you tried and abandoned, what constraints shaped the decision — evaporates. Six months later, someone asks "why did you do it this way?" and nobody remembers.

This tool exists to close that gap. It installs instructions that make GitHub Copilot a persistent decision logger, capturing reasoning as a natural byproduct of the conversation you're already having.

The design follows the [Human-AI Intent Transfer Principles](https://mgrandau.medium.com/human-ai-intent-transfer-principles-b6e7404e3d26?source=friends_link&sk=858917bd3f4a686974ed6b6c9c059ac8): the core idea is that **the journal is the intent transfer mechanism** — it externalizes and persists the context that would otherwise live only in a chat window. Every rejected alternative documented is optionality preserved. Every decision record is rationale made inspectable.

These principles shaped the project itself: the [project plan](docs/PROJECT_PLAN.md) documents goals and risk posture per phase, and the [journal entry](docs/journal/daily.journal.2026.02.20.md) captures every design alternative explored and why it was rejected.

This isn't about documentation for documentation's sake. It's about making your future self (and your future AI) smarter about your codebase.

📝 [Follow the Knowledge (That's the Context)](https://mgrandau.medium.com/follow-the-knowledge-thats-the-context-7860c47e5fc8?source=friends_link&sk=eb124f0721a90fd8d45314f0a34ca6cb) — The thinking behind why capturing decisions and context matters.

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
| --- | --- |
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
- `prompts/setup-dendron-vault.prompt.md` — on-demand Dendron vault setup

### Global (all repos)

```bash
copilot-journal --global
```

Installs all three files to your VS Code User `prompts/` directory.

### Options

```bash
copilot-journal --journal-path my/journal  # Custom journal location
copilot-journal --global --insiders        # VS Code Insiders
copilot-journal --dry-run                  # Preview without copying
copilot-journal --log-level DEBUG          # Verbose output
```

When run interactively, the installer will prompt you for the journal path:

```text
📓 Where should journal entries be stored? [docs/journal]: 
```

Press Enter to accept the default (`docs/journal`) or type a custom path.

## Journal Setup

After installing the instructions, create your journal directory in your project:

```bash
mkdir -p docs/journal    # or whatever path you specified during install
```

Copilot will write daily entries like `docs/journal/2026-02-18.md` with timestamped entries capturing your reasoning as you work.

## Project Context

Key files for understanding the project's architecture and conventions:

| Path | Purpose |
| --- | --- |
| [src/copilot_journal/README.md](src/copilot_journal/README.md) | Architecture & design overview |
| [docs/journal/](docs/journal/) | Decision journal — the "why" behind changes |
| [.github/instructions/project.instructions.md](.github/instructions/project.instructions.md) | Project conventions & workflows |
| [skill/copilot-journal/SKILL.md](skill/copilot-journal/SKILL.md) | OpenClaw skill definition |
| [utils/README.md](utils/README.md) | Utility scripts reference |

## OpenClaw Skill

This repo also includes an [OpenClaw](https://github.com/openclaw/openclaw) skill at `skill/copilot-journal/`. To install it, copy the skill folder to your OpenClaw skills directory:

```bash
cp -r skill/copilot-journal /path/to/openclaw/skills/
```

This gives OpenClaw agents the same journaling workflow — capture decisions, reasoning, and context automatically.

## Community

💬 [Join the Discord community](https://discord.gg/2KqjHvh5)

## License

MIT
