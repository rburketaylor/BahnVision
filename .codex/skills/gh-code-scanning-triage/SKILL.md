---
name: gh-code-scanning-triage
description: Quickly triage GitHub code scanning alerts and determine whether findings are currently actionable or blocked by missing upstream fixes. Use when asked to check active code scanning issues, summarize alert counts/severity, or answer whether alerts can be fixed now.
---

# Gh Code Scanning Triage

## Overview

Use this skill to answer code scanning status questions in under two minutes.
Prioritize one-pass triage: gather open alerts, classify fixable vs no-fix-yet, then report direct next actions.

## Quick Start

Run:

```bash
./.codex/skills/gh-code-scanning-triage/scripts/check-alerts.sh
```

Filter to one branch or produce JSON:

```bash
./.codex/skills/gh-code-scanning-triage/scripts/check-alerts.sh --ref refs/heads/main
./.codex/skills/gh-code-scanning-triage/scripts/check-alerts.sh --format json
```

## Workflow

1. Run the script once to collect all open alerts.
2. Read `actionable now` and `no-fix-yet` counts.
3. Confirm per-alert details from the table: alert number, CVE/rule, severity, package, installed version, fixed version.
4. Conclude:

- If `fixed` is empty, treat as not directly remediable now.
- If `fixed` has a version, treat as actionable now.

5. Report the exact alert URLs and one recommended next step.

## Decision Rules

- Classify as `actionable` only when `Fixed Version` is non-empty.
- Classify as `no-fix-yet` when `Fixed Version` is empty.
- Note duplicate-looking findings as separate alerts when they affect different packages (for example `libc6` and `libc-bin`).

## Optional Deep Check

Run only when needed:

```bash
gh api repos/<owner>/<repo>/code-scanning/alerts/<alert-number>
gh api repos/<owner>/<repo>/code-scanning/alerts/<alert-number>/instances
```

Use this to confirm branch/ref spread or tool metadata without redoing full CI/log analysis.

## Resources (optional)

### scripts/

Use `scripts/check-alerts.sh` for fast triage output.
