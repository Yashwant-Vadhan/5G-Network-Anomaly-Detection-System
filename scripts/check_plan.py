import collections
import re
import sys

files = sys.argv[1:] or ["todo_v2.md", "todo_v2_1.md"]
T = {}
for f in files:
    txt = open(f, encoding="utf-8").read()
    for m in re.finditer(r"#### (T\d+-\d+): (.*?)\n(.*?)(?=\n#### T|\n## |\Z)", txt, re.S):
        i, title, b = m.groups()
        st = re.search(r"\*\*Status:\*\*\s*(\S+)", b)
        dp = re.search(r"\*\*Dependencies:\*\*\s*(.*)", b)
        ef = re.search(r"\*\*Estimated Effort:\*\*\s*(\d+)", b)
        ow = re.search(r"\*\*Owner:\*\*\s*(\w+)", b)
        deps = (
            [
                d.strip()
                for d in (dp.group(1).split(",") if dp else [])
                if d.strip() and d.strip() != "None"
            ]
            if dp
            else []
        )
        T[i] = {
            "status": st.group(1) if st else "?",
            "deps": deps,
            "eff": int(ef.group(1)) if ef else 0,
            "owner": ow.group(1) if ow else "?",
        }


def ph(i):
    return int(i.split("-")[0][1:])


dead = {i for i, x in T.items() if x["status"] == "⛔"}
act = {i: x for i, x in T.items() if i not in dead}
bad = []
for i, x in act.items():
    if x["eff"] not in (15, 30, 45, 60, 90):
        bad.append(("effort", i, x["eff"]))
    for d in x["deps"]:
        if d not in T:
            bad.append(("missing dep", i, d))
        elif d in dead:
            bad.append(("depends on superseded", i, d))

memo = {}
vis = set()


def lp(i):
    if i in memo:
        return memo[i]
    if i in vis:
        bad.append(("cycle", i, ""))
        return (0, [])
    vis.add(i)
    best = (0, [])
    for d in act[i]["deps"]:
        if d in act:
            c = lp(d)
            if c[0] > best[0]:
                best = c
    vis.discard(i)
    memo[i] = (best[0] + act[i]["eff"], best[1] + [i])
    return memo[i]


cp = lp("T14-019") if "T14-019" in act else (0, [])
EDGE = {f"T12-0{n}" for n in range(11, 19)}


def tot(f):
    d = collections.defaultdict(float)
    for i, x in act.items():
        if ph(i) != 15 and f(i):
            d[x["owner"]] += x["eff"] / 60
    return {k: round(v, 2) for k, v in d.items()}


print("tasks active/superseded:", len(act), len(dead))
print("problems:", bad or "none")
print("hours (edge incl.):", tot(lambda i: True))
print("hours (edge dropped):", tot(lambda i: i not in EDGE))
print("critical path to T14-019: %.2f h" % (cp[0] / 60))
print(" -> ".join(cp[1]))
print("T14-018 deps:", T.get("T14-018", {}).get("deps"))
