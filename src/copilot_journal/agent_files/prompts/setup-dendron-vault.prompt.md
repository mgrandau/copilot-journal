---
description: "Initialize a Dendron vault in docs/journal/ with dendron.yml, VS Code settings, and .gitignore entries."
---

# Set Up Dendron Journal Vault

Initialize a Dendron vault in `docs/journal/` — git-tracked, accessible via the Dendron VS Code extension.

## 1. Create Vault Directory

Create `docs/journal/` if missing.

## 2. Vault Root Files

`docs/journal/root.md`:

```markdown
---
id: root
title: root
desc: "Project journal vault root"
updated: {{TIMESTAMP}}
created: {{TIMESTAMP}}
---
```

`docs/journal/root.schema.yml`:

```yaml
version: 1
imports: []
schemas:
  - id: root
    title: root
    parent: root
```

## 3. `dendron.yml` at Workspace Root

Create or merge into existing `dendron.yml`. If vault `docs/journal` already listed, skip.

```yaml
version: 5
publishing:
  enableFMTitle: true
  enableHierarchyDisplay: true
  enableNoteTitleForLink: true
preview:
  enableFMTitle: true
workspace:
  vaults:
    - fsPath: docs/journal
      name: journal
  journal:
    dailyDomain: daily
    dailyVault: journal
    name: journal
    dateFormat: "y.MM.dd"
    addBehavior: childOfDomain
  enableAutoCreateOnDefinition: true
  enableXVaultWikiLink: false
```

## 4. VS Code Settings

Merge into `.vscode/settings.json` (preserve existing settings):

```json
{ "dendron.rootDir": "." }
```

## 5. `.gitignore`

Add if missing (do **not** ignore `docs/journal/`):

```
.dendron.*
seeds
```

## 6. Initial Daily Note

`docs/journal/daily.journal.{{YYYY}}.{{MM}}.{{DD}}.md` — local date/time for all values:

```markdown
---
id: {{GENERATE_UUID}}
title: "{{Month DD, YYYY}}"
desc: ""
updated: {{TIMESTAMP}}
created: {{TIMESTAMP}}
---

# Journal - {{Month DD, YYYY}}

First entry. Dendron vault initialized for project journaling.
```

## 7. Verify

- `docs/journal/` has `root.md` and `root.schema.yml`
- `dendron.yml` at workspace root references the vault
- `.vscode/settings.json` has `dendron.rootDir`
- `.gitignore` has `.dendron.*` and `seeds`
- Tell user to reload VS Code (`Developer: Reload Window`)
