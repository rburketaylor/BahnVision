#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: check-alerts.sh [options]

Quickly triage GitHub code scanning alerts and classify fixability.

Options:
  --repo <owner/repo>     Override repository autodetection from git origin
  --state <state>         Alert state (default: open)
  --ref <git-ref>         Filter by ref (example: refs/heads/main)
  --format <table|json>   Output format (default: table)
  -h, --help              Show this help text
EOF
}

require_bin() {
  local bin="$1"
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Missing required command: $bin" >&2
    exit 1
  fi
}

detect_repo() {
  local origin_url candidate
  origin_url="$(git remote get-url origin 2>/dev/null || true)"
  if [[ -z "$origin_url" ]]; then
    echo "Could not detect GitHub repository from git origin. Use --repo owner/repo." >&2
    exit 1
  fi

  candidate="${origin_url#*github.com[:/]}"
  candidate="${candidate%.git}"

  if [[ ! "$candidate" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
    echo "Could not parse owner/repo from origin URL: $origin_url" >&2
    echo "Use --repo owner/repo." >&2
    exit 1
  fi

  echo "$candidate"
}

REPO=""
STATE="open"
REF=""
FORMAT="table"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --state)
      STATE="${2:-}"
      shift 2
      ;;
    --ref)
      REF="${2:-}"
      shift 2
      ;;
    --format)
      FORMAT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$FORMAT" != "table" && "$FORMAT" != "json" ]]; then
  echo "Invalid --format: $FORMAT (expected table or json)" >&2
  exit 1
fi

require_bin gh
require_bin jq

if [[ -z "$REPO" ]]; then
  REPO="$(detect_repo)"
fi

api_args=(
  -X GET
  "repos/${REPO}/code-scanning/alerts"
  -f "state=${STATE}"
  -f "per_page=100"
)

if [[ -n "$REF" ]]; then
  api_args+=(-f "ref=${REF}")
fi

alerts_json="$(gh api "${api_args[@]}")"

normalized_json="$(jq '
  map({
    number,
    cve: (.rule.id // .rule.name // ""),
    severity: (.rule.security_severity_level // .rule.severity // ""),
    package: ((.most_recent_instance.message.text // "") | try capture("Package: (?<v>[^\\n]+)").v catch ""),
    installed_version: ((.most_recent_instance.message.text // "") | try capture("Installed Version: (?<v>[^\\n]+)").v catch ""),
    fixed_version: ((.most_recent_instance.message.text // "") | try capture("Fixed Version: (?<v>[^\\n]*)").v catch ""),
    ref: (.most_recent_instance.ref // ""),
    url: .html_url
  })
' <<<"$alerts_json")"

if [[ "$FORMAT" == "json" ]]; then
  jq '.' <<<"$normalized_json"
  exit 0
fi

total_count="$(jq 'length' <<<"$normalized_json")"
actionable_count="$(jq '[.[] | select(.fixed_version != "")] | length' <<<"$normalized_json")"
no_fix_count="$(jq '[.[] | select(.fixed_version == "")] | length' <<<"$normalized_json")"

echo "repo: ${REPO}"
if [[ -n "$REF" ]]; then
  echo "ref: ${REF}"
else
  echo "ref: all"
fi
echo "state: ${STATE}"
echo "open alerts: ${total_count}"
echo "actionable now (fixed version available): ${actionable_count}"
echo "no-fix-yet: ${no_fix_count}"

if [[ "$total_count" -eq 0 ]]; then
  exit 0
fi

echo
{
  printf "alert\tcve\tseverity\tpackage\tinstalled\tfixed\tref\turl\n"
  jq -r '
    sort_by(.number)[] |
    [
      (.number | tostring),
      .cve,
      .severity,
      .package,
      .installed_version,
      .fixed_version,
      .ref,
      .url
    ] | @tsv
  ' <<<"$normalized_json"
} | column -ts $'\t'
