---
name: atomic-commits
description: Validate, repair, plan, and create atomic git commits with clear Conventional Commits messages. Use when the user asks to "organize commits", "plan commits", "make atomic commits", or commit current work cleanly without pushing. Inspect diffs, run repo-appropriate checks before planning, fix validation failures, propose a confirmed commit plan, then stage and commit each group with staged-file hook checks.
---

# Atomic Commits

Create a small set of self-contained commits with descriptive messages from a worktree that has already passed relevant validation.

Core rule: run targeted validation before proposing the commit plan. Fix failures first so the plan reflects the final, validated diff instead of obsolete broken changes.

## Workflow

### 1) Inspect changes

```bash
git status
git diff
git diff --staged
git log --oneline -10
```

Identify:

- Existing staged changes vs unstaged changes
- Untracked files that may need inclusion
- Files that look unrelated to the requested work
- Generated, lockfile, migration, or snapshot changes that may need special handling

Do not revert user changes. If unrelated changes are present, leave them alone and exclude them from the commit plan unless the user asks to include them. If the worktree already has staged changes, preserve that staging intent: either include those staged changes as-is in the plan, or ask before unstaging/restaging them. Do not use broad reset commands to clean the index; avoid `git reset`, and never use `git reset --hard`. When unstaging is explicitly approved, prefer path-limited `git restore --staged <files>` or interactive staging that preserves the working tree.

### 2) Validate and repair before planning

Run targeted checks based on what changed before presenting any commit plan. Prefer fast, relevant checks over broad suites, but include enough coverage to catch likely failures.

Examples (repo-specific; use only if they exist in the repo):

```bash
# Backend
pytest backend/tests
mypy --config-file backend/mypy.ini backend/app

# Frontend
(cd frontend && npm run lint)
(cd frontend && npm run type-check)
(cd frontend && npm run test -- --run)

# Tracked changed files, when pre-commit is available
git diff --name-only --diff-filter=ACMRTUXB -z HEAD | xargs -0 -r pre-commit run --files
```

Selection guidance:

- Python/backend changes: run relevant pytest targets; add mypy when typed app code changed.
- TypeScript/frontend changes: run lint, type-check, and relevant Vitest tests.
- E2E-facing UI behavior changes: run the targeted Playwright spec when practical.
- Config, CI, dependency, or formatting changes: run the matching formatter/linter/hook.
- If only docs changed, validation may be limited to spelling/link or formatting checks that exist in the repo.

If checks fail:

- Fix straightforward failures that are clearly part of the requested work before planning commits.
- Ask before making broad repairs, touching unrelated files, or changing behavior outside the requested work.
- Re-run the failed checks, plus any checks affected by the fix.
- Repeat until targeted validation passes or a blocker remains.
- If a blocker cannot be fixed safely, report it and do not proceed to commit planning unless the user explicitly chooses to continue.

After validation passes, re-run `git status` and inspect the final diff again. Use this post-validation diff for planning.

### 3) Propose an atomic commit plan

Group changes into commits that are:

- Buildable/testable in isolation
- Logically cohesive (avoid mixing formatting, refactors, and behavior changes unless required)
- Ordered so dependencies land first
- Based on the validated final diff, including any fixes made during validation

Use this format when presenting the plan:

```
Planned commits (N total):

1. <type>(<optional-scope>): <subject>
   Files: path/a, path/b
   Why: <what + why in 1–3 bullets>
```

Ask for confirmation before creating commits.

### 4) Create commits one by one

For each planned commit:

```bash
# Stage only what belongs to this commit (use -p when you need hunk-level staging)
git add <files>
# or: git add -p

# Confirm something is staged before running hooks or committing
git diff --cached --quiet && { echo "No staged changes for this commit"; exit 1; }

# Run pre-commit only on the files staged for this commit
git diff --cached --name-only -z | xargs -0 -r pre-commit run --files

# If hooks modified files, inspect the changes, then stage only intended files/hunks
git diff
git add <files>
git diff --cached --name-only -z | xargs -0 -r pre-commit run --files

# Double-check the staged diff
git diff --staged

# Commit with a properly formatted multi-line message
git commit -F - <<'EOF'
<type>(<optional-scope>): <subject>

<what changed>
<why it changed>
EOF
```

Before each commit, confirm `git diff --staged` contains only that commit's intended changes. If nothing is staged, stop and fix the staging instead of creating an empty commit. If staged-file hooks fail, fix and re-run them before committing. If a fix changes the planned grouping, pause and update the plan with the user.

Do not push. Avoid `--amend` unless the user explicitly requests it.

### 5) Optional full-repo check (manual/on-demand)

Do not run `pre-commit run --all-files` automatically.

Use pre-plan targeted checks and per-commit staged-file hooks as the default validation path. Run a full-repo pre-commit check only when the user explicitly asks for it, or when preparing for a release-level validation pass.

If the user requests a full-repo check, prefer running it before creating commits. If it fails, fix the issues and update the commit plan before committing. If a full-repo check is run after commits already exist and it fails, report the failure and ask before creating follow-up commits.

Do not push. The user pushes manually.

### 6) Verify and report

```bash
git log --oneline -10
git status
```

Report:

- The commits created (subjects + high-level contents)
- What checks were run and whether they passed
- Any validation failures fixed before planning
- Whether a full-repo pre-commit check was run or intentionally skipped
- Reminder that commits are local and not pushed
