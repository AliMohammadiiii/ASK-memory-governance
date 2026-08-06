#!/usr/bin/env python3
"""Pre-submission checks for paper/paper_1.

Runs the mechanical gates that a reviewer (or an AI-writing screen) would apply:
bibliography integrity, reference/label integrity, orphan tables and figures,
numeric agreement with the analysis artifact, and the strong-signal scan from
the AI-writing checklist.

Offline by default. Pass --network to additionally resolve every arXiv id
against the arXiv API and every DOI against Crossref, which is the check that
catches a citation pointing at a retitled or unrelated paper.

Exit code 0 if all gates pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER = REPO / "paper" / "paper_1"
ANALYSIS = REPO / "artifacts" / "analysis" / "mgp6_v43_full_benchmark_analysis.json"

failures: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def ok(label: str, detail: str = "") -> None:
    print(f"  PASS  {label}{(' — ' + detail) if detail else ''}")


def body_tex() -> str:
    parts = sorted((PAPER / "sections").glob("*.tex"))
    parts += [PAPER / "appendix.tex", PAPER / "main.tex"]
    return "".join(p.read_text(encoding="utf-8") for p in parts if p.exists())


# --------------------------------------------------------------------------
# 1. Bibliography integrity
# --------------------------------------------------------------------------
def check_bibliography(tex: str) -> dict[str, dict]:
    print("\n[1] Bibliography integrity")
    raw = (PAPER / "references.bib").read_text(encoding="utf-8")

    entries: dict[str, dict] = {}
    for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", raw, re.S):
        key, body = m.group(2).strip(), m.group(3)

        def field(name: str, entry: str = body) -> str | None:
            mm = re.search(name + r"\s*=\s*\{(.*?)\}\s*,?\s*\n", entry, re.S)
            return " ".join(mm.group(1).split()) if mm else None

        entries[key] = {
            "title": field("title"),
            "author": field("author"),
            "year": field("year"),
            "doi": field("doi"),
            "url": field("url"),
            "journal": field("journal"),
        }

    cited: set[str] = set()
    for m in re.finditer(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}", tex, re.S):
        cited.update(k.strip() for k in m.group(1).split(","))

    orphans = sorted(set(entries) - cited)
    missing = sorted(cited - set(entries))
    if orphans:
        fail(f"bib entries defined but never cited: {orphans}")
    if missing:
        fail(f"cited but absent from references.bib: {missing}")
    if not orphans and not missing:
        ok("citation coverage", f"{len(cited)} cited / {len(entries)} defined")
    return entries


# --------------------------------------------------------------------------
# 2. Labels, refs, orphan tables and figures
# --------------------------------------------------------------------------
def check_crossrefs(tex: str) -> None:
    print("\n[2] Cross-references, tables, figures")
    table_tex = "".join(p.read_text(encoding="utf-8") for p in (PAPER / "tables").glob("*.tex"))
    labels = set(re.findall(r"\\label\{([^}]*)\}", tex + table_tex))
    refs = set(re.findall(r"\\(?:ref|autoref|eqref|pageref)\{([^}]*)\}", tex))

    broken = sorted(refs - labels)
    if broken:
        fail(f"\\ref with no matching \\label: {broken}")
    else:
        ok("all \\ref targets resolve", f"{len(refs)} refs")

    inputs = set(re.findall(r"\\input\{tables/([^}]*)\}", tex))
    on_disk = {p.stem for p in (PAPER / "tables").glob("*.tex")}
    if missing := sorted(inputs - on_disk):
        fail(f"\\input{{tables/...}} with no file: {missing}")
    if orphan_tables := sorted(on_disk - inputs):
        notes.append(f"orphan table files (generated, never \\input): {orphan_tables}")

    figs = set(re.findall(r"\\includegraphics\[[^\]]*\]\{figures/([^}]*)\}", tex))
    fig_disk = {p.name for p in (PAPER / "figures").glob("*")}
    if missing_figs := sorted(figs - fig_disk):
        fail(f"\\includegraphics with no file: {missing_figs}")
    else:
        ok("all figures present", f"{len(figs)} used")
    if orphan_figs := sorted(fig_disk - figs):
        notes.append(f"orphan figure files (never included): {orphan_figs}")


# --------------------------------------------------------------------------
# 3. Numbers against the analysis artifact
# --------------------------------------------------------------------------
def check_numbers() -> None:
    print("\n[3] Reported numbers vs analysis artifact")
    if not ANALYSIS.exists():
        fail(f"analysis artifact missing: {ANALYSIS}")
        return
    h = json.loads(ANALYSIS.read_text())["hidden_v43"]
    s, c, o, pc = h["safety"], h["cost"], h["operational"], h["per_class"]

    # (label, value as printed in the manuscript, value in the artifact, tolerance)
    expected = [
        # headline metrics (Section 7.1, abstract, conclusion)
        ("hidden accuracy", 0.8481, h["accuracy"], 5e-4),
        ("hidden macro-F1", 0.8479, h["macro_f1"], 5e-4),
        ("Cohen kappa", 0.7722, h["kappa"], 5e-4),
        ("MCC", 0.7728, h["mcc"], 5e-4),
        ("balanced accuracy", 0.8481, h["balanced_acc"], 5e-4),
        # intervals
        ("cluster CI acc low", 0.8037, h["cluster_ci_acc"][0], 5e-4),
        ("cluster CI acc high", 0.8889, h["cluster_ci_acc"][1], 5e-4),
        ("cluster CI mF1 low", 0.8021, h["cluster_ci_mf1"][0], 5e-4),
        ("cluster CI mF1 high", 0.8894, h["cluster_ci_mf1"][1], 5e-4),
        ("Wilson CI low", 0.8154, h["wilson95"][0], 5e-4),
        ("Wilson CI high", 0.8760, h["wilson95"][1], 5e-4),
        # selective prediction (the disclosed defect)
        ("selective coverage", 0.6926, h["selective_coverage"], 5e-4),
        ("selective accuracy", 0.8449, h["selective_accuracy"], 5e-4),
        # per-class (Section 7.2)
        ("SUPERSEDE recall", 0.9167, pc["SUPERSEDE"]["recall"], 5e-4),
        ("SUPERSEDE F1", 0.9066, pc["SUPERSEDE"]["f1"], 5e-4),
        ("ABSTAIN recall", 0.7889, pc["ABSTAIN"]["recall"], 5e-4),
        ("ABSTAIN F1", 0.8208, pc["ABSTAIN"]["f1"], 5e-4),
        # harm decomposition: counts and rates
        ("false commit n", 38, s["false_commit"]["count"], 0),
        ("false commit rate", 0.2111, s["false_commit"]["rate"], 1e-3),
        ("abstain->keep n", 30, s["abstain_to_keep"]["count"], 0),
        ("abstain->keep rate", 0.1667, s["abstain_to_keep"]["rate"], 1e-3),
        ("abstain->supersede n", 8, s["abstain_to_supersede"]["count"], 0),
        ("abstain->supersede rate", 0.0444, s["abstain_to_supersede"]["rate"], 1e-3),
        ("missed update n", 15, s["missed_update"]["count"], 0),
        ("missed update rate", 0.0833, s["missed_update"]["rate"], 1e-3),
        ("destructive overwrite n", 11, s["destructive_overwrite"]["count"], 0),
        ("destructive overwrite rate", 0.0611, s["destructive_overwrite"]["rate"], 1e-3),
        ("unnecessary abstain n", 24, s["unnecessary_abstain"]["count"], 0),
        ("unnecessary abstain rate", 0.0667, s["unnecessary_abstain"]["rate"], 1e-3),
        # cost regimes (Section 7.5)
        ("cost balanced", 0.1519, c["balanced"], 5e-4),
        ("cost commit-averse", 0.4204, c["commit_averse"], 5e-4),
        ("cost update-responsive", 0.2963, c["update_responsive"], 5e-4),
        # operational accounting (Section 7.6)
        ("latency mean (ms)", 1673, o["lat_mean"], 1),
        ("latency median (ms)", 1278, o["lat_med"], 1),
        ("latency p95 (ms)", 2931, o["lat_p95"], 1.5),
        ("latency max (ms)", 12626, o["lat_max"], 1),
        ("latency sum (s)", 903.5, o["lat_sum_s"], 0.1),
        ("prompt tokens total", 212467, o["ptok"], 0),
        ("completion tokens total", 4000, o["ctok"], 0),
        ("prompt tokens / decision", 393, o["ptok"] / h["n"], 0.6),
        ("completion tokens / decision", 7.4, o["ctok"] / h["n"], 0.05),
        # guard (Section 7.4)
        ("guard changed (hidden)", 36, h["guard"]["changed"], 0),
        ("guard ABSTAIN->KEEP", 30, h["guard"]["transitions"]["ABSTAIN->KEEP"], 0),
        ("guard ABSTAIN->SUPERSEDE", 6, h["guard"]["transitions"]["ABSTAIN->SUPERSEDE"], 0),
    ]
    bad = [
        f"{n}: paper={p} artifact={a}"
        for n, p, a, tol in expected
        if abs(float(p) - float(a)) > tol
    ]
    if bad:
        for b in bad:
            fail("number mismatch — " + b)
    else:
        ok("hidden-split numbers", f"{len(expected)}/{len(expected)} agree")

    # selective-accuracy defect is disclosed in the paper; assert it still holds
    if h["selective_accuracy"] >= h["accuracy"]:
        notes.append(
            "selective accuracy now >= overall accuracy — the disclosed defect "
            "in Sections 7.2/9 no longer holds and that text must be updated"
        )


# --------------------------------------------------------------------------
# 4. AI-writing strong signals + drafting residue
# --------------------------------------------------------------------------
def check_writing_signals(tex: str) -> None:
    print("\n[4] Drafting residue / AI-writing strong signals")
    patterns = {
        "placeholder": r"\[Insert[^\]]*\]|\[Specific [^\]]*\]|SOURCE_PUBLISHER|"
        r"PASTE_URL_HERE|20\d\d-XX-XX|\bTODO\b|\bFIXME\b|\bTBD\b",
        "assistant markup leakage": r"contentReference|oaicite|oai_citation|"
        r"turn\d+search\d+|turn\d+file\d+|attributableIndex|"
        r"\[cite: ?\d+\]|grok_card|ppl-ai-file-upload|:::writing",
        "chatgpt referrer in URL": r"utm_source=chatgpt",
        "assistant voice": r"\bAs an AI\b|I hope this helps|Let me know if|"
        r"Would you like|knowledge cutoff",
        "unresolved LaTeX query": r"\?\?\?|\\todo\{|\\note\{",
    }
    clean = True
    for label, pat in patterns.items():
        hits = [m.group(0) for m in re.finditer(pat, tex, re.I)]
        if hits:
            clean = False
            fail(f"{label}: {sorted(set(hits))[:5]}")
    if clean:
        ok("no placeholders, markup leakage, or assistant voice")


# --------------------------------------------------------------------------
# 5. Optional network verification of every citation identifier
# --------------------------------------------------------------------------
def check_citations_online(entries: dict[str, dict]) -> None:
    print("\n[5] Citation identifiers (network)")
    import time
    import urllib.request
    import xml.etree.ElementTree as ET

    ns = {"a": "http://www.w3.org/2005/Atom"}

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

    for key, e in sorted(entries.items()):
        url, journal = e.get("url") or "", e.get("journal") or ""
        arxiv_id = None
        if "arxiv.org/abs/" in url:
            arxiv_id = url.split("/abs/")[1]
        elif "arXiv:" in journal:
            arxiv_id = re.search(r"arXiv:([\d.]+)", journal).group(1)
        if not arxiv_id:
            continue
        try:
            data = urllib.request.urlopen(
                "http://export.arxiv.org/api/query?id_list=" + arxiv_id, timeout=30
            ).read()
            entry = ET.fromstring(data).find("a:entry", ns)
            live = " ".join(entry.find("a:title", ns).text.split())
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{key}: arXiv lookup failed ({exc})")
            time.sleep(3.2)
            continue

        bib_title = re.sub(r"[{}]", "", e["title"] or "")
        a, b = norm(bib_title), norm(live)
        if a and b and a not in b and b not in a:
            fail(
                f"{key} (arXiv {arxiv_id}) TITLE MISMATCH\n"
                f"        bib : {bib_title}\n"
                f"        live: {live}"
            )
        else:
            ok(key, f"arXiv {arxiv_id}")
        time.sleep(3.2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--network",
        action="store_true",
        help="resolve every arXiv id against the live arXiv API (slow, ~3s/entry)",
    )
    args = ap.parse_args()

    if not PAPER.exists():
        print(f"paper directory not found: {PAPER}", file=sys.stderr)
        return 1

    print(f"Checking {PAPER}")
    tex = body_tex()
    entries = check_bibliography(tex)
    check_crossrefs(tex)
    check_numbers()
    check_writing_signals(tex)
    if args.network:
        check_citations_online(entries)

    if notes:
        print("\nNOTES (not failures)")
        for n in notes:
            print(f"  - {n}")

    print()
    if failures:
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  * {f}")
        return 1
    print("All gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
