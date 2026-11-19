#!/usr/bin/env python3
"""PreToolUse guard for the ripperdoc subagent.

Write/Edit: only inside a `ripperdoc_reviews/` directory or the ripperdoc scratch root.
Bash: every segment of a command must start with one of ripperdoc's own tools: `sandbox-run`
(whole filesystem read-only, no network) or `validate.py` / `render_dossier.py`. There is no
allowlist of "read-only" host commands: too many of them can write or execute (git -c,
rg --pre, sed e/w, sort -o, ...). Reading goes through the Read/Grep/Glob tools or sandbox-run.
Only RIPPERDOC_TIMEOUT may be set in front of a command (BASH_ENV, LD_PRELOAD, PATH, ... would
change how the host-side sandbox-run script itself runs).
Redirections may only target /dev/null, fds, a ripperdoc_reviews/ dir or the scratch root.
Command/process substitution outside single quotes is refused (the host shell would run it).
Exit 2 = block; the stderr message is shown to the agent.
"""
import json, os, re, shlex, sys

BIN = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "bin"))
SCRATCH = {os.path.realpath(os.environ.get("RIPPERDOC_SCRATCH") or os.path.join(os.environ.get("TMPDIR") or "/tmp", "ripperdoc")),
           "/tmp/ripperdoc"}
OWN_TOOLS = {"sandbox-run", "validate.py", "render_dossier.py"}
ENV_OK = {"RIPPERDOC_TIMEOUT"}
SEPS = {";", "&&", "||", "|", "&", "|&", "(", ")"}
REDIR = re.compile(r"^\d*(>>?|>\||&>>?|>&)$")
HINT = ("Run it inside the sandbox instead: {bin}/sandbox-run <cmd> (or sandbox-run bash -c '...'); "
        "only $RIPPERDOC_OUT is writable there. To read files use the Read, Grep and Glob tools. "
        "Save your own reports with the Write tool under ripperdoc_reviews/.").format(bin=BIN)


def deny(msg):
    print(f"ripperdoc guard: {msg}", file=sys.stderr)
    sys.exit(2)


def allowed_path(p, cwd):
    if not p:
        return False
    p = os.path.realpath(os.path.join(cwd, os.path.expanduser(p)))
    if "ripperdoc_reviews" in p.split(os.sep):
        return True
    return any(p == r or p.startswith(r + os.sep) for r in SCRATCH)


def own_tool(word, cwd):
    word = os.path.expanduser(os.path.expandvars(word))
    return os.path.basename(word) in OWN_TOOLS and os.path.realpath(os.path.join(cwd, os.path.dirname(word) or ".")) == BIN


def check_segment(words, cwd):
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
        name = words[0].split("=", 1)[0]
        if name not in ENV_OK:
            deny(f"setting {name} in front of a command is not allowed (only {', '.join(sorted(ENV_OK))}).")
        words = words[1:]
    if not words:
        return
    w0, base = words[0], os.path.basename(words[0])
    if base == "cd" and len(words) <= 2:
        return
    if own_tool(w0, cwd):
        return
    if base in ("python", "python3") and len(words) > 1 and own_tool(words[1], cwd) and os.path.basename(words[1]) != "sandbox-run":
        return
    deny(f"`{base}` would run on the host. {HINT}")


def check_bash(cmd, cwd):
    unquoted = re.sub(r"'[^']*'", "''", cmd)
    if re.search(r"\$\(|`|<\(|>\(", unquoted):
        deny("command or process substitution would run outside the sandbox; put it inside sandbox-run bash -c '...'.")
    lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        toks = list(lex)
    except ValueError as e:
        deny(f"could not parse the command ({e}); simplify it or use sandbox-run bash -c '...'.")
    seg, i = [], 0
    while i < len(toks):
        t = toks[i]
        if REDIR.match(t) or t in (">", ">>"):
            tgt = toks[i + 1] if i + 1 < len(toks) else ""
            if not (tgt.startswith("&") or tgt.isdigit() or tgt in ("/dev/null", "/dev/stdout", "/dev/stderr")
                    or (t.endswith(">&") and tgt.isdigit()) or allowed_path(tgt, cwd)):
                deny(f"redirect to `{tgt}` would write outside ripperdoc_reviews/ or the scratch root.")
            i += 2
            continue
        if t in ("<", "<<", "<<<"):
            i += 2
            continue
        if t in SEPS:
            check_segment(seg, cwd)
            seg = []
        else:
            seg.append(t)
        i += 1
    check_segment(seg, cwd)


def main():
    data = json.load(sys.stdin)
    tool, ti = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    cwd = data.get("cwd") or os.getcwd()
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = ti.get("file_path") or ti.get("notebook_path")
        if not allowed_path(path, cwd):
            deny(f"{tool} to {path} refused: ripperdoc writes only inside a ripperdoc_reviews/ directory "
                 f"or the scratch root. Give fixes to the producer as instructions instead.")
    elif tool == "Bash":
        check_bash(ti.get("command", ""), cwd)
    sys.exit(0)


if __name__ == "__main__":
    main()
