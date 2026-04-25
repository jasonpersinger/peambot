#!/usr/bin/env bash
set -euo pipefail

mode="${1:-working-tree}"

case "$mode" in
  staged)
    mapfile -t files < <(git diff --cached --name-only --diff-filter=ACMR)
    grep_args=(--cached)
    ;;
  working-tree)
    mapfile -t files < <(git ls-files --cached --others --exclude-standard)
    grep_args=()
    ;;
  *)
    echo "usage: $0 [staged|working-tree]" >&2
    exit 2
    ;;
esac

[ "${#files[@]}" -eq 0 ] && exit 0

for file in "${files[@]}"; do
  case "$file" in
    .env|.env.*)
      if [ "$file" != ".env.example" ]; then
        echo "secret scan: refusing to include $file" >&2
        exit 1
      fi
      ;;
    data/.config.yaml|data/*.yaml|data/*.yml|data/*.json)
      case "$file" in
        data/.mcp_server_settings.example.json|data/.mcp_server_settings.json|data/.config.yaml.template)
          # safe to commit — no secrets, no substituted values
          ;;
        *)
          echo "secret scan: refusing to include generated/private server config $file" >&2
          exit 1
          ;;
      esac
      ;;
  esac
done

patterns=(
  'AIza[0-9A-Za-z_-]{20,}'
  'gsk_[0-9A-Za-z]{20,}'
  'sk_[0-9a-f]{30,}'
  'm0-[0-9A-Za-z]{20,}'
)

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

for pattern in "${patterns[@]}"; do
  if git grep -n -I -E "${grep_args[@]}" "$pattern" -- "${files[@]}" >"$tmpfile" 2>/dev/null; then
    echo "secret scan: possible API key found:" >&2
    sed -n '1,20p' "$tmpfile" >&2
    exit 1
  fi
done

