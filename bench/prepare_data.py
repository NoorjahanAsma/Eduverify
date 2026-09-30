"""Build bench/items.jsonl: 15 chart items (ChartQA test tables) + 15 diagram items (AI2D annotations).
ChartQA: https://github.com/vis-nlp/ChartQA (GPL-3.0). AI2D: https://allenai.org/data/diagrams (CC BY-SA 4.0 / see license.txt).
Deterministic (seed 0). Downloaded raw data is cached in bench/data/ (gitignored)."""
from __future__ import annotations
import csv, io, json, random, re, urllib.parse, urllib.request
from pathlib import Path

D = Path(__file__).parent / "data"; D.mkdir(exist_ok=True)
SEED = 0


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "eduverify-bench"}), timeout=60).read()


def num(s: str):
    s = s.strip().replace(",", "").replace("%", "").replace("$", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return None if v != v else v  # NaN cell = missing data


def charts(n=15, exclude=(), absent=False):
    api = "https://api.github.com/repos/vis-nlp/ChartQA/contents/ChartQA%20Dataset/test/tables"
    names = [x["name"] for x in json.loads(get(api))]
    rng = random.Random(SEED); rng.shuffle(names)
    items = []
    for nm in names:
        if len(items) == n:
            break
        if nm in exclude:
            continue
        raw = get(f"https://raw.githubusercontent.com/vis-nlp/ChartQA/main/ChartQA%20Dataset/test/tables/{urllib.parse.quote(nm)}").decode("utf-8", "ignore")
        (D / nm).write_text(raw)
        rows = list(csv.reader(io.StringIO(raw)))
        if len(rows) < 4 or len(rows) > 9 or not (2 <= len(rows[0]) <= 4):
            continue
        head, body = rows[0], rows[1:]
        cols = list(zip(*body))
        vals = [[num(c) for c in col] for col in cols[1:]]
        raw_ok = all(re.fullmatch(r"\s*(nan|-?[\d,]*\.?\d+\s*%?|\$?-?[\d,]*\.?\d+)\s*", c, re.I) for col in cols[1:] for c in col)
        if not raw_ok or all(v is None for col in vals for v in col) or any(all(v is None for v in col) for col in vals) or any(len(set(c.strip() for c in cols[0])) != len(body) for _ in [0]):
            continue
        cats = [c.strip() for c in cols[0]]
        yearlike = all(re.fullmatch(r"(19|20)\d\d", c) for c in cats)
        ctype = "line" if yearlike else "bar"
        series = {h.strip(): v for h, v in zip(head[1:], vals)}
        md = "| " + " | ".join(head) + " |\n|" + "---|" * len(head) + "\n" + "\n".join("| " + " | ".join(r) + " |" for r in body)
        if absent:  # withhold the last row from the source but ask for it: correct behaviour is to omit it or abstain
            if len(body) < 4:
                continue
            hidden = cats[-1]
            body, cats = body[:-1], cats[:-1]
            series = {h: v[:-1] for h, v in series.items()}
            md = "| " + " | ".join(head) + " |\n|" + "---|" * len(head) + "\n" + "\n".join("| " + " | ".join(r) + " |" for r in body)
            req = f"Make a {ctype} chart of this table for a classroom slide. Use every row and every column, and include {hidden} as well."
        else:
            req = f"Make a {ctype} chart of this table for a classroom slide. Use every row and every column."
        items.append(dict(id=f"{'chartabs' if absent else 'chart'}_{len(items):02d}", kind="chart", subset="chart_absent" if absent else "chart_full",
                          ctype=ctype, src_id=nm, request=req, source=md, gt=dict(categories=cats, series=series), **(dict(withheld=hidden) if absent else {})))
    return items


def diagrams(n=15):
    from remotezip import RemoteZip
    z = RemoteZip("https://ai2-public-datasets.s3.amazonaws.com/diagrams/ai2d-all.zip")
    cat = json.loads(z.read("ai2d/categories.json"))
    rng = random.Random(SEED)
    plan = [("foodChainsWebs", 8), ("lifeCycles", 7)]
    items = []
    for c, quota in plan:
        files = [k for k, v in cat.items() if v == c]; rng.shuffle(files)
        got = 0
        for f in files:
            if got == quota:
                break
            a = json.loads(z.read(f"ai2d/annotations/{f}.json"))
            lab = {}  # blob -> label(s)
            for r in a["relationships"].values():
                if r["category"] == "intraObjectLabel" and r["destination"].startswith("B"):
                    lab.setdefault(r["destination"], []).append(a["text"][r["origin"]]["value"].strip())
            edges = [(r["origin"], r["destination"]) for r in a["relationships"].values()
                     if r["category"] == "interObjectLinkage" and r.get("hasDirectionality")]
            if not edges or any(b not in lab or len(lab[b]) != 1 for e in edges for b in e):
                continue
            nodes = sorted({b for e in edges for b in e})
            labels = [lab[b][0].title() for b in nodes]
            if not (4 <= len(nodes) <= 8) or len(set(labels)) != len(labels) or len(edges) < 3:
                continue
            ed = sorted({(lab[a_][0].title(), lab[b_][0].title()) for a_, b_ in edges})
            what = "food chain or food web" if c == "foodChainsWebs" else "life cycle"
            rule = "Each arrow points in the direction energy flows (from the food to the eater)." if c == "foodChainsWebs" else "Arrows follow the order of the stages."
            items.append(dict(id=f"diagram_{len(items):02d}", kind="diagram", subset="diagram_thin", category=c, src_id=f,
                              request=f"Draw a {what} diagram that uses exactly these labeled parts and shows the arrows between them. {rule}",
                              source="Labels: " + "; ".join(labels), gt=dict(nodes=labels, edges=[list(e) for e in ed])))
            (D / f"ai2d_{f}").write_bytes(z.read(f"ai2d/images/{f}"))
            sents = [(f"{b} eats {a}." if c == "foodChainsWebs" else f"{a} is followed by {b}.") for a, b in ed]
            random.Random(SEED + len(items)).shuffle(sents)
            it = items[-1]
            items.append(dict(it, id=it["id"].replace("diagram_", "diagramrel_"), subset="diagram_rel",
                              source=it["source"] + "\n" + " ".join(sents)))
            got += 1
    return items


if __name__ == "__main__":
    ch = charts(); items = ch + diagrams() + charts(exclude={c['src_id'] for c in ch}, absent=True)
    out = Path(__file__).parent / "items.jsonl"
    out.write_text("\n".join(json.dumps(i) for i in items) + "\n")
    print(len(items), "items ->", out)
