#!/bin/bash
# SessionStart hook (Claude Code cloud sessions): install / verify every tool before the session starts, so nothing races the install.
set -euo pipefail
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then exit 0; fi
exec bash "${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}/scripts/bootstrap.sh"
