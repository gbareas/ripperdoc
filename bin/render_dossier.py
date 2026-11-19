#!/usr/bin/env python3
"""Render ripperdoc_reviews/dossier.json into DOSSIER.md next to it (human view; the JSON is the source).

  render_dossier.py <path/to/ripperdoc_reviews/dossier.json>
"""
import json, os, subprocess, sys

def cell(x):
    return str(x if x not in (None, "") else "").replace("|", "\\|").replace("\n", " ")

def table(rows, cols):
    if not rows:
        return "_none_\n"
    out = ["| " + " | ".join(c for c, _ in cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(cell(f(r)) for _, f in cols) + " |" for r in rows]
    return "\n".join(out) + "\n"

def main():
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(2)
    src = os.path.realpath(sys.argv[1])
    if "ripperdoc_reviews" not in src.split(os.sep):
        sys.exit("render_dossier: dossier.json must live in a ripperdoc_reviews/ directory")
    v = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.realpath(__file__)), "validate.py"), "dossier", src],
                       capture_output=True, text=True)
    if v.returncode:
        sys.exit("render_dossier: dossier.json is invalid, fix it first:\n" + v.stdout)
    d = json.load(open(src))
    p = d["project"]
    md = [f"# Dossier: {p['name']}", "",
          f"_Generated from `dossier.json` (updated {d['updated']}). Edit the JSON, not this file._", "",
          f"**Root:** `{p['root']}`  ", f"**Goal:** {p['goal']}", "", "**Research questions**", ""]
    md += [f"- {q}" for q in p["research_questions"]] or ["_none recorded_"]
    md += ["", "## Hypotheses", "", table(d["hypotheses"], [
        ("id", lambda h: h["id"]), ("statement", lambda h: h["statement"]), ("status (producer)", lambda h: h["status"]),
        ("origin", lambda h: h["origin"]), ("pre-reg", lambda h: ("yes: " + h.get("frozen_ref", "")) if h["pre_registered"] else "no"),
        ("ripperdoc", lambda h: h.get("ripperdoc_assessment", "")), ("source", lambda h: h["source"])])]
    md += ["## Work done", "", table(d["work_done"], [
        ("id", lambda w: w["id"]), ("what", lambda w: w["what"]), ("result", lambda w: w.get("result", "")),
        ("status", lambda w: w["status"]), ("tests", lambda w: ", ".join(w.get("tests_hypotheses", []))),
        ("review", lambda w: w["review"] + (f" ({w['review_file']})" if w.get("review_file") else "")), ("source", lambda w: w["source"])])]
    md += ["## Literature", "", table(d["literature"], [
        ("key", lambda l: l["key"]), ("claim", lambda l: l["claim"]), ("relevance", lambda l: l["relevance"]),
        ("bears on", lambda l: ", ".join(l.get("bears_on", []))), ("found via", lambda l: l["found_via"]),
        ("read", lambda l: l["read_by_ripperdoc"]), ("ref", lambda l: l.get("url") or l["citation"])])]
    ls = d.get("literature_search")
    md += [f"_Web search: {ls['date']}, queries: " + "; ".join(f"`{q}`" for q in ls["queries"]) + "_" if ls
           else "_No web literature search run (only on request)._", ""]
    md += ["## Conventions", "", table(d["conventions"], [("name", lambda c: c["name"]), ("rule", lambda c: c["rule"]), ("source", lambda c: c["source"])])]
    md += ["## Where things are", "", table(d["locations"], [("what", lambda c: c["what"]), ("path", lambda c: f"`{c['path']}`")])]
    md += ["## Known risks", ""] + ([f"- {r}" for r in d["risks"]] or ["_none_"])
    md += ["", "## Gaps (could not find)", ""] + ([f"- {g}" for g in d["gaps"]] or ["_none_"])
    md += ["", "## Sources read", "", table(d["sources_read"], [("path", lambda s: f"`{s['path']}`"), ("kind", lambda s: s["kind"]), ("mtime", lambda s: s["mtime"])])]
    out = os.path.join(os.path.dirname(src), "DOSSIER.md")
    open(out, "w").write("\n".join(md))
    print(f"wrote {out}")

if __name__ == "__main__":
    main()
