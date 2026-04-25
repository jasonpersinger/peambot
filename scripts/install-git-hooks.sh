#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"

cat >"$repo_root/.git/hooks/pre-commit" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
scripts/check-secrets.sh staged
HOOK

cat >"$repo_root/.git/hooks/pre-push" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
scripts/check-secrets.sh working-tree
HOOK

chmod +x "$repo_root/.git/hooks/pre-commit" "$repo_root/.git/hooks/pre-push"
echo "Installed Peambot Git secret-scan hooks."

