---
name: atomic-commits
description: Plan and create organized atomic commits with detailed descriptions. Use when the user wants to commit changes with proper organization - the skill will analyze changes, group them into logical atomic commits, run the full test suite to verify, resolve any issues, and make commits without pushing.
---

# Atomic Commits Skill

This skill helps you create organized, atomic commits with detailed descriptions. It ensures all tests pass before committing by running the full validation suite.

## When to Use

Invoke this skill when:

- User wants to commit current changes with proper organization
- User asks to "plan commits" or "organize commits"
- User wants to ensure tests pass before committing
- User mentions "atomic commits" or "detailed commit messages"

## Workflow

### Step 1: Analyze Changes

First, gather information about the current state:

```bash
# Get overview of changes
git status

# See detailed diffs
git diff HEAD

# Check recent commit history for style reference
git log --oneline -10
```

### Step 2: Plan Atomic Commits

Analyze the changes and group them into logical atomic commits. Each commit should:

- Be self-contained and buildable
- Contain logically related changes
- Follow Conventional Commits format: `<type>: <description>`
- Have a detailed body explaining the what and why

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

### Step 4: Run Full Test Suite

Before committing, run the full validation suite based on what files changed:

```bash
# Backend-only changes
source backend/.venv/bin/activate
pre-commit run --all-files
pytest backend/tests

# Frontend-only changes
cd frontend && npm run lint
cd frontend && npm run type-check
cd frontend && npm run test -- --run

# Mixed changes - run all of the above
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
git commit -m "$(cat <<'EOF'
<type>: <brief description>

<detailed explanation of changes>

EOF
)"
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
git log --oneline -N
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
