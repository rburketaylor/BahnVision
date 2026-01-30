---
name: atomic-commits
description: Plan and create organized atomic commits with clear Conventional Commits messages. Use when the user asks to "organize commits", "plan commits", "make atomic commits", or commit current work cleanly. Analyze diffs, propose a commit plan for confirmation, run repo-appropriate checks (pre-commit/pytest and/or frontend lint/typecheck/tests), then stage and commit each group without pushing.
---

# Atomic Commits Skill

Create a small set of self-contained commits with descriptive messages and verified checks.

## Workflow

### Step 1: Analyze Changes

Gather information about the current state:

```bash
git status

git diff
git diff --staged

git log --oneline -10
```

### Step 2: Plan Atomic Commits

Analyze the changes and group them into logical atomic commits. Each commit should:

- Be self-contained and buildable
- Contain logically related changes
- Follow Conventional Commits format: `<type>: <description>`
- Have a detailed body explaining the what and why

**Grouping guidance:**

- Group by **feature**, not by file. If changes across multiple files implement a single feature, commit them together.
- A "feature" typically includes: backend implementation, frontend wiring, and any related type/model changes.
- Only split when changes are truly independent (e.g., a feature vs. its test updates vs. unrelated docs).
- Avoid over-granular commits that split a single coherent change just because it touches many files.

Common commit types:

- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring (no behavior change)
- `chore:` - Maintenance tasks, dependencies, config
- `docs:` - Documentation changes
- `test:` - Test changes
- `build:` - Build system or dependency changes
- `perf:` - Performance improvements

### Step 3: Present the Plan

Before committing, present the planned commits to the user in a clear format:

```
Planned commits (N total):

1. [type]: brief description
   Files: path/to/file1, path/to/file2
   Details: explanation of what changes and why

2. [type]: brief description
   Files: path/to/file3
   Details: explanation of what changes and why
```

Ask for user confirmation before proceeding.

### Step 4: Run Appropriate Checks

Before committing, run checks appropriate to what changed (prefer targeted checks; run broader checks for risky/wide changes). If this repo uses `direnv`, ensure it is allowed; otherwise activate the dev env (often `source .dev-env`) before running Python tooling.

```bash
# Safe baseline for most repos (if configured)
pre-commit run --all-files

# Backend changes
pytest backend/tests

# Frontend changes
(cd frontend && npm run lint)
(cd frontend && npm run type-check)
(cd frontend && npm run test -- --run)

# Mixed changes: run both backend and frontend checks
```

Continue to Step 5 only after all checks pass.

### Step 5: Resolve Issues

If any tests fail or linting errors occur:

1. Fix the issues
2. Re-run the failing checks
3. Repeat until all checks pass
4. Only then proceed to create commits

### Step 6: Create Commits

Create commits one at a time, staging only the files for each commit:

```bash
# For each planned commit:
git add <files-for-this-commit>
git commit -F - <<'EOF'
<type>: <brief description>

<detailed explanation of changes>

EOF
```

**IMPORTANT:**

- Always use HEREDOC syntax for commit messages to ensure proper formatting
- Each commit must be created separately (never batch multiple logical commits)
- Do NOT use `git commit --amend` - always create new commits
- Do NOT push commits - the skill only creates them locally

### Step 7: Verify and Report

After all commits are created:

```bash
# Show the commits created
git log --oneline -10
git status
```

Report to the user:

- Number of commits created
- Brief summary of each commit
- Confirmation that tests passed
- Reminder that commits are local and not pushed

## Example Output

After completing, report to the user like this:

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

All tests passed. Commits are ready locally (not pushed).
```

## Important Notes

- **Never skip tests** - Always run the full test suite before committing
- **Never push** - This skill only creates local commits
- **Always use HEREDOC** for commit message formatting
- **Always create new commits** - never amend existing ones
- **Group logically** - Atomic commits should be self-contained units
- **Follow project style** - Match existing commit message patterns
