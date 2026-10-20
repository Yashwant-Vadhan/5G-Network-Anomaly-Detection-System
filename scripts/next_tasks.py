#!/usr/bin/env python3
"""List the tasks an owner can start now, from todo_v2.md + todo_v2_1.md.
Usage: python scripts/next_tasks.py Yashwant|Sushil [--human] [todo_v2.md todo_v2_1.md]
--human lists Human-only tasks whose dependencies are all done (ready for YOU)
Eligible = status ⬜/🔄, owner matches, every dependency ✅, not Human-only/UNCLEAR/Optional,
not edge (T12-011..T12-018), not Phase 15. Run `git pull --rebase` first."""

import re
import sys

args = [a for a in sys.argv[1:] if a != "--human"]
HUMAN_MODE = "--human" in sys.argv
owner = args[0] if args else sys.exit(__doc__)
files = args[1:] or ["todo_v2.md", "todo_v2_1.md"]
T = {}
for f in files:
    txt = open(f, encoding="utf-8").read()
    for m in re.finditer(r"#### (T\d+-\d+): (.*?)\n(.*?)(?=\n#### T|\n## |\Z)", txt, re.S):
        i, title, b = m.groups()
        st = re.search(r"\*\*Status:\*\*\s*(.*)", b)
        dp = re.search(r"\*\*Dependencies:\*\*\s*(.*)", b)
        ef = re.search(r"\*\*Estimated Effort:\*\*\s*(\d+)", b)
        ow = re.search(r"\*\*Owner:\*\*\s*(\w+)", b)
        sline = st.group(1) if st else ""
        T[i] = dict(
            title=title,
            sline=sline,
            mark=(sline.strip().split() or ["?"])[0],
            deps=[
                d.strip()
                for d in (dp.group(1).split(",") if dp else [])
                if d.strip() and d.strip() != "None"
            ],
            eff=int(ef.group(1)) if ef else 0,
            owner=ow.group(1) if ow else "?",
        )
EDGE = {f"T12-0{n}" for n in range(11, 19)}
ANDROID = {"T12-002", "T12-003", "T12-004", "T12-007", "T12-008"}
OWNER_ACTION = {"T18-009", "T18-010"}  # need repo/hosting settings changed by the owner
ph = lambda i: int(i.split("-")[0][1:])
elig, blocked, skipped, done = [], [], [], 0
for i, x in sorted(T.items()):
    if x["owner"] != owner:
        continue
    if x["mark"] == "✅":
        done += 1
        continue
    if x["mark"] == "⛔":
        continue
    flags = x["sline"] + " " + x["title"]
    if HUMAN_MODE:
        if "Human-only" in flags:
            w = [d for d in x["deps"] if T.get(d, {}).get("mark") != "✅"]
            (blocked if w else elig).append(
                (
                    i,
                    [
                        (d, T.get(d, {}).get("owner", "?"), T.get(d, {}).get("mark", "missing"))
                        for d in w
                    ],
                )
                if w
                else (i, x["title"], x["eff"], [])
            )
        continue
    if "Human-only" in flags or "UNCLEAR" in flags:
        skipped.append((i, "human/unclear"))
        continue
    if "Optional" in flags or i in EDGE or ph(i) == 15:
        skipped.append((i, "optional/edge/phase15"))
        continue
    waiting = [d for d in x["deps"] if T.get(d, {}).get("mark") != "✅"]
    if waiting:
        blocked.append(
            (
                i,
                [
                    (d, T.get(d, {}).get("owner", "?"), T.get(d, {}).get("mark", "missing"))
                    for d in waiting
                ],
            )
        )
        continue
    note = []
    if i.startswith("T19") or i in ANDROID:
        note.append("needs Android build")
    if i in OWNER_ACTION:
        note.append("needs owner action in hosting/repo settings")
    elig.append((i, x["title"], x["eff"], note))
print(
    f"{owner}: {done} done, {len(elig)} eligible now, {len(blocked)} waiting on dependencies, {len(skipped)} skipped"
)
print("\nELIGIBLE (do in this order):")
for i, t, e, n in elig:
    print(f"  {i}  {t}  [{e} min]" + (f"  <{'; '.join(n)}>" if n else ""))
print("\nWAITING ON DEPENDENCIES:")
for i, w in blocked:
    print(f"  {i}: " + ", ".join(f"{d}({o}, {m})" for d, o, m in w))
print("\nSKIPPED (needs a human, optional, or gated):")
print("  " + ", ".join(f"{i}[{why}]" for i, why in skipped))
