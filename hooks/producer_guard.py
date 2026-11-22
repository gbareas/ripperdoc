#!/usr/bin/env python3
"""PreToolUse hook for the producer's session: the producer may not write what judges it.

Blocks Write/Edit/MultiEdit/NotebookEdit into a ripperdoc_reviews/ directory (or the policy's
review_dir), into .ripperdoc/policy.json or .ripperdoc/state/, and into the Ripperdoc installation
(SKILL.md, packs, hooks, bin, schema). Claim manifests in .ripperdoc/claims/ stay writable: declaring a
claim is the producer's job. Bash commands that mention any of those paths, or the gate's environment
variable, are blocked too; this is a best-effort text check, so the real guarantee is the gate's own
record: a report the gate did not record, or that changed afterwards, never passes.
Reviewer sessions started by the gate (RIPPERDOC_GATE_ACTIVE=1) are not checked here; they have their
own guard (hooks/guard.py). Exit 2 = block; stderr is shown to the agent.
"""
import json, os, re, sys

RD = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
GATE_ENV = "RIPPERDOC_GATE_ACTIVE"
MARKERS = ("ripperdoc_reviews", ".ripperdoc/policy", ".ripperdoc/state", GATE_ENV)
# Running the gate itself is allowed (it is how a producer asks for a review), as a plain command only.
GATE_CMD = re.compile(r"^\s*\S*ripperdoc-gate\s+(check|review)\s+[\w./-]+\s*$")


def deny(msg):
    print(f"ripperdoc producer guard: {msg}", file=sys.stderr)
    sys.exit(2)


def find_root(cwd):
    d = os.path.realpath(cwd)
    while True:
        if os.path.isdir(os.path.join(d, ".ripperdoc")) or os.path.isdir(os.path.join(d, ".git")):
            return d
        if os.path.dirname(d) == d:
            return os.path.realpath(cwd)
        d = os.path.dirname(d)


def review_dir_name(root):
    try:
        return json.load(open(os.path.join(root, ".ripperdoc", "policy.json"))).get("review_dir") or "ripperdoc_reviews"
    except (OSError, ValueError):
        return "ripperdoc_reviews"


def protected(path, cwd):
    if not path:
        return None
    root = find_root(cwd)
    p = os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))
    inside = lambda base: p == base or p.startswith(base + os.sep)
    if "ripperdoc_reviews" in p.split(os.sep) or inside(os.path.join(root, review_dir_name(root))):
        return "reviews are written only by Ripperdoc"
    if p == os.path.join(root, ".ripperdoc", "policy.json"):
        return "the gate policy is written only by a human"
    if inside(os.path.join(root, ".ripperdoc", "state")):
        return "gate state is written only by the gate"
    if inside(RD):
        return "the Ripperdoc installation is not part of the work"
    return None


def main():
    if os.environ.get(GATE_ENV):
        sys.exit(0)
    data = json.load(sys.stdin)
    tool, ti = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    cwd = data.get("cwd") or os.getcwd()
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = ti.get("file_path") or ti.get("notebook_path")
        why = protected(path, cwd)
        if why:
            deny(f"{tool} to {path} refused: {why}. Fix the work itself; read reports with the Read tool.")
    elif tool == "Bash":
        cmd = ti.get("command", "")
        if GATE_CMD.match(cmd):
            sys.exit(0)
        rd_dir = review_dir_name(find_root(cwd))
        for m in MARKERS + (RD, rd_dir if rd_dir != "ripperdoc_reviews" else "ripperdoc_reviews"):
            if m and m in cmd:
                deny(f"this command touches `{m}`, which the producer may not change. "
                     "Read Ripperdoc's reports with the Read tool; fix the work itself.")
    sys.exit(0)


if __name__ == "__main__":
    main()
