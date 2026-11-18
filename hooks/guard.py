#!/usr/bin/env python3
"""PreToolUse guard for the ripperdoc subagent.

Write/Edit: only inside a `ripperdoc_reviews/` directory or the ripperdoc scratch root.
Bash: a command is allowed when every segment is either read-only (allowlist below),
`sandbox-run ...` (whole filesystem read-only), or one of ripperdoc's own bin/ tools.
Redirections may only target /dev/null, fds, a ripperdoc_reviews/ dir or the scratch root.
Command/process substitution outside single quotes is refused (it would run unsandboxed).
Exit 2 = block; the stderr message is shown to the agent.
"""
import json, os, re, shlex, sys

BIN = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "bin"))
SCRATCH = {os.path.realpath(os.environ.get("RIPPERDOC_SCRATCH") or os.path.join(os.environ.get("TMPDIR") or "/tmp", "ripperdoc")),
           "/tmp/ripperdoc"}
OWN_TOOLS = {"sandbox-run", "validate.py", "render_dossier.py"}
READ_ONLY = set("""cat head tail wc ls stat file find grep egrep fgrep rg sort uniq cut tr column diff cmp comm
md5sum sha1sum sha256sum du df tree realpath readlink basename dirname pwd echo printf date jq nl od xxd
hexdump strings pdftotext pdfinfo pdffonts h5ls h5dump ncdump true false test [ cd which type printenv
whoami hostname uname nvidia-smi sed git""".split())
GIT_OK = {"log", "show", "diff", "status", "blame", "ls-files", "ls-tree", "rev-parse", "cat-file", "grep",
          "describe", "shortlog", "reflog", "rev-list", "merge-base", "whatchanged"}
SEPS = {";", "&&", "||", "|", "&", "|&", "(", ")"}
REDIR = re.compile(r"^\d*(>>?|>\||&>>?|>&)$")
HINT = ("Run it inside the sandbox instead: {bin}/sandbox-run <cmd> (or sandbox-run bash -c '...'); "
        "only $RIPPERDOC_OUT is writable there. Save your own reports with the Write tool under ripperdoc_reviews/.").format(bin=BIN)


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


def own_tool(word):
    word = os.path.expanduser(os.path.expandvars(word))
    return os.path.basename(word) in OWN_TOOLS and os.path.realpath(os.path.dirname(word) or ".") == BIN


def check_segment(words, cwd):
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
        words = words[1:]
    if not words:
        return
    w0, base = words[0], os.path.basename(words[0])
    if own_tool(w0):
        return
    if base in ("python", "python3") and len(words) > 1 and own_tool(words[1]):
        return
    if base not in READ_ONLY:
        deny(f"`{base}` is not on the read-only list. {HINT}")
    if base == "find" and any(a in ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprintf", "-fls") for a in words):
        deny("find with -delete/-exec/-fprint is not allowed. " + HINT)
    if base == "sed" and any(a.startswith("-i") or a.startswith("--in-place") for a in words):
        deny("sed -i edits files; the producer's work is read-only.")
    if base == "sed" and any(re.search(r"(^|[;}\s])w\s", a) for a in words[1:]):
        deny("sed write command (w) is not allowed. " + HINT)
    if base == "git":
        rest = words[1:]
        while rest and rest[0].startswith("-"):
            rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
        sub = rest[0] if rest else ""
        if sub not in GIT_OK:
            deny(f"git {sub or '(none)'} is not read-only. Allowed: {', '.join(sorted(GIT_OK))}. Never stage or commit.")
        if any(a.startswith("--output") for a in rest):
            deny("git --output writes a file.")


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
