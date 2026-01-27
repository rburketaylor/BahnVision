---
name: atomic-commits
description: Plan and create atomic git commits with clear Conventional Commits messages. Use when the user asks to "organize commits", "plan commits", "make atomic commits", or commit current work cleanly (without pushing). Analyze diffs, propose a commit plan for confirmation, run repo-appropriate checks (pre-commit/pytest and/or frontend lint/typecheck/tests), then stage and commit each group.
---

# Atomic Commits

Create a small set of self-contained commits with descriptive messages and verified checks.

## Workflow

### 1) Inspect changes

```bash
git status
git diff
git diff --staged
git log --oneline -10
```

### 2) Propose an atomic commit plan

Group changes into commits that are:

- Buildable/testable in isolation
- Logically cohesive (avoid mixing formatting, refactors, and behavior changes unless required)
- Ordered so dependencies land first

Use this format when presenting the plan:

```
Planned commits (N total):

1. <type>(<optional-scope>): <subject>
   Files: path/a, path/b
   Why: <what + why in 1–3 bullets>
```

Ask for confirmation before creating commits.

### 3) Run repo-appropriate checks

Prefer targeted checks based on what changed; run broader checks for risky/wide changes.

Common baseline:

```bash
pre-commit run --all-files
```

Examples (repo-specific; use only if they exist in the repo):

```bash
# Backend
pytest backend/tests

# Frontend
(cd frontend && npm run lint)
(cd frontend && npm run type-check)
(cd frontend && npm run test -- --run)
```

If checks fail: fix, then re-run the failing checks before committing.

### 4) Create commits one by one

For each planned commit:

```bash
# Stage only what belongs to this commit (use -p when you need hunk-level staging)
git add <files>
# or: git add -p

# Double-check the staged diff
git diff --staged

# Commit with a properly formatted multi-line message
git commit -F - <<'EOF'
<type>(<optional-scope>): <subject>

<what changed>
<why it changed>
EOF
```

Do not push. Avoid `--amend` unless the user explicitly requests it.

### 5) Verify and report

```bash
git log --oneline -10
git status
```

Report:

- The commits created (subjects + high-level contents)
- What checks were run and whether they passed
- Reminder that commits are local and not pushed
