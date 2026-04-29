---
name: atomic-commits
description: Plan and create organized atomic commits with clear Conventional Commits messages. Use when the user asks to "organize commits", "plan commits", "make atomic commits", or commit current work cleanly. Analyze diffs, propose a commit plan for confirmation, run pre-commit --all-files ONCE before creating commits, then stage and commit each group without pushing.
---

# Atomic Commits Skill

Create a small set of self-contained commits with descriptive messages and verified checks.

---

## Workflow

### Step 1: Gather State (no destructive actions)

Inspect the current state of the repository:

```bash
# Goal: identify all modified, staged, and untracked files that belong to this change set
git status
git diff            # all unstaged modifications
git diff --staged   # any previously staged changes
git log --oneline -10
```

**GUARD: Do NOT run `git reset` here.** If there are already staged changes:

1. Ask the user: _"You have N files already staged. Should I unstage before planning, or plan around them?"_
2. Only unstaged if the user explicitly says to — and even then, use `git reset HEAD -- <file>` per-file, never a bare `git reset`.

If the staging area is clean, proceed directly to Step 2.

### Step 2: Plan Atomic Commits

Analyze the diffs and group changes into logical atomic commits. Each commit should:

- Be self-contained and buildable
- Contain logically related changes
- Follow Conventional Commits format: `<type>: <description>`
- Have a detailed body explaining the what and why

**Grouping guidance:**

- Group by **feature**, not by file. If changes across multiple files implement a single feature, commit them together.
- A "feature" typically includes: backend implementation, frontend wiring, and any related type/model changes.
- **Bundle code and tests together.** The pre-commit test hook runs pytest/vitest on every commit, so a code commit without its corresponding test updates will fail. Always include test changes in the same commit as the code they test.
- Only split when changes are truly independent (e.g., a feature vs. unrelated docs vs. unrelated refactors).
- Avoid over-granular commits that split a single coherent change just because it touches many files.

Common commit types:

- `feat:` — New feature
- `fix:` — Bug fix
- `refactor:` — Code refactoring (no behavior change)
- `chore:` — Maintenance tasks, dependencies, config
- `docs:` — Documentation changes
- `test:` — Test changes
- `build:` — Build system or dependency changes
- `perf:` — Performance improvements

For each planned commit, identify which **functions, classes, or sections** belong to it (not just which files). This will be used later to verify that the right hunks are staged.

### Step 3: Run All Checks and Resolve Issues

**Do this BEFORE presenting the plan to the user**, because `pre-commit --all-files` may auto-modify files (e.g., formatting), which can change the commit plan.

Run checks ONCE for all changes:

```bash
pre-commit run --all-files
```

If this repo uses `direnv`, ensure it is allowed before running. Otherwise activate the dev env (often `source .dev-env`) before running Python tooling.

**If checks pass:** proceed to Step 4.

**If checks fail:**

1. Fix the issues.
2. Re-run `pre-commit run --all-files` (not individual checks).
3. If checks still fail after **3 fix attempts**, **STOP** and report the failure to the user with the full output. Ask for direction. Do not loop beyond 3 attempts.
4. **CRITICAL: Do NOT proceed to create commits until all checks pass.**

After checks pass, re-examine the plan from Step 2. If `pre-commit` auto-modified any files, adjust the commit groupings accordingly before presenting.

### Step 4: Present and Confirm the Plan

Present the verified plan to the user:

```
Planned commits (N total):

1. [type]: brief description
   Scope: <functions/sections this commit covers>
   Files: path/to/file1, path/to/file2
   Details: explanation of what changes and why

2. [type]: brief description
   Scope: <functions/sections this commit covers>
   Files: path/to/file3
   Details: explanation of what changes and why
```

Ask for user confirmation before proceeding.

### Step 5: Create Commits

**GUARD: Only proceed here after the user has confirmed the plan AND all pre-commit checks have passed.**

Create commits one at a time. For each planned commit:

```bash
# Stage only the files for this commit
git add <files-for-this-commit>

# CRITICAL: Verify what will actually be committed
git diff --cached    # Goal: confirm staged hunks match ONLY this commit's scope
```

**Review the staged diff carefully:**

- Does it contain ONLY the changes described in this commit's scope?
- Are there unrelated changes bundled in? (especially if a single file has changes for multiple commits)
- If wrong changes are staged, use `git reset HEAD -- <file>` to unstage that specific file, then re-stage more carefully.
- Do NOT use bare `git reset` — it unstages ALL files and destroys your commit-in-progress.

After verifying the staged diff matches the planned commit:

```bash
git commit -F - <<'EOF'
<type>: <brief description>

<detailed explanation of changes>

EOF
```

**GUARD: If `git commit` fails** (e.g., pre-commit hook rejects it):

1. Do NOT amend — fix the issue and create a new commit attempt.
2. If the failure suggests the plan was wrong, **stop the sequence**, report what commits were created and what failed, and ask the user how to proceed.
3. Only continue to the next planned commit after the current one succeeds.

**Rules for creating commits:**

- Always verify with `git diff --cached` BEFORE committing.
- Always use HEREDOC syntax for commit messages.
- Each commit must be created separately (never batch multiple logical commits).
- Do NOT use `git add -p` or any interactive command — use file-level staging only.
- Do NOT use `git commit --amend` — always create new commits.
- Do NOT push commits — the skill only creates them locally.
- Pre-commit hooks will run during each `git commit`. This is expected and safe because you already passed `--all-files` in Step 3.

### Step 6: Verify and Report

After all commits are created:

```bash
# Goal: confirm all intended commits were created and working tree is clean
git log --oneline -10
git status
```

Report to the user:

- Number of commits created
- Brief summary of each commit
- Confirmation that checks passed
- Reminder that commits are local and not pushed

---

## Example Output

```
✓ Created 3 atomic commits:

  1. feat: add user authentication middleware
     - Added JWT token validation
     - Implemented login/logout endpoints
     - Added user session management

  2. refactor: extract validation logic to shared module
     - Moved validators to backend/app/api/v1/shared/
     - Updated all endpoints to use shared validators
     - Reduced code duplication

  3. docs: update API documentation for auth endpoints
     - Added authentication flow diagrams
     - Documented token refresh mechanism

All checks passed. Commits are ready locally (not pushed).
```

---

## Troubleshooting

| Problem                                             | Action                                                                                                                                                                                             |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| User had pre-staged work                            | Ask whether to preserve or unstage before planning. Unstaged per-file with `git reset HEAD -- <file>`, never bare `git reset`.                                                                     |
| `pre-commit --all-files` fails                      | Fix and re-run. After 3 failed fix attempts, stop and ask the user.                                                                                                                                |
| Auto-formatting changed files                       | Re-examine the commit plan — those changes may need different grouping.                                                                                                                            |
| Wrong files staged for a commit                     | `git reset HEAD -- <file>` to unstage specific files, not bare `git reset`.                                                                                                                        |
| `git commit` rejected by hook                       | Fix the issue, then create a new commit (never amend). If the fix changes the plan, stop the sequence and ask.                                                                                     |
| A file has changes for multiple commits             | Split at file boundaries (whole-file per commit). Interactive `git add -p` is not supported; stage files as wholes only. If a file truly needs splitting, ask the user to split it manually first. |
| Partial sequence failure (2 of 3 commits succeeded) | Report what was created and what failed. Ask user whether to continue, re-plan, or start over. Never amend already-created commits.                                                                |
