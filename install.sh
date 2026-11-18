#!/usr/bin/env bash
# Install Ripperdoc into Claude Code (user level).
#   ~/.claude/agents/ripperdoc.md               <- agents/ripperdoc.md
#   ~/.claude/skills/experiment-review/SKILL.md <- skills/experiment-review/SKILL.md
# Both are generated from templates with this checkout's path filled in, so the repo stays
# the source of truth: edit here, then rerun ./install.sh. Existing files are backed up (*.bak).
set -euo pipefail
RD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$RD" in "$HOME"/*) RD_STR="\$HOME/${RD#"$HOME"/}";; *) RD_STR="$RD";; esac
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
command -v bwrap >/dev/null || echo "warning: bwrap (bubblewrap) not found; sandbox-run will refuse to rerun code" >&2

install_one() {  # template destination
  mkdir -p "$(dirname "$2")"
  local tmp; tmp="$(mktemp)"
  sed "s|__RIPPERDOC_HOME__|$RD_STR|g" "$1" > "$tmp"
  if [[ -f "$2" ]] && ! cmp -s "$tmp" "$2"; then cp "$2" "$2.bak"; echo "backed up $2 -> $2.bak"; fi
  mv "$tmp" "$2"; echo "installed $2"
}
install_one "$RD/agents/ripperdoc.md" "$CLAUDE_DIR/agents/ripperdoc.md"
install_one "$RD/skills/experiment-review/SKILL.md" "$CLAUDE_DIR/skills/experiment-review/SKILL.md"
chmod +x "$RD"/bin/* "$RD"/hooks/*.py
echo "done. Restart Claude Code (or open /agents) to load the agent."
