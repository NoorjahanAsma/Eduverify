from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .ir import load_ir
from .pipeline import run, generate_and_run
from .llm import get_llm


def _src(a):
    return Path(a).read_text() if a else None


def main(argv=None):
    p = argparse.ArgumentParser("eduverify")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("render", "verify"):
        s = sub.add_parser(name); s.add_argument("ir"); s.add_argument("--source"); s.add_argument("-o", "--out", default="out")
        s.add_argument("--vlm", help="provider:model for read-back, e.g. ollama:qwen3-vl:8b"); s.add_argument("--no-ocr", action="store_true")
    g = sub.add_parser("generate"); g.add_argument("request"); g.add_argument("--source"); g.add_argument("--kind", choices=["chart", "diagram", "infographic"])
    g.add_argument("--provider", default="ollama"); g.add_argument("--model"); g.add_argument("--vlm"); g.add_argument("--repairs", type=int, default=2); g.add_argument("-o", "--out", default="out")
    a = p.parse_args(argv)

    def vlm_of(spec):
        if not spec:
            return None
        prov, _, model = spec.partition(":")
        return get_llm(prov, model or None)

    if a.cmd == "generate":
        rep = generate_and_run(a.request, get_llm(a.provider, a.model), a.out, _src(a.source), a.kind, vlm_of(a.vlm), a.repairs)
    else:
        ir = load_ir(Path(a.ir).read_text())
        if a.cmd == "verify":
            from .verify import rules
            issues = rules.check(ir, _src(a.source))
            for i in issues:
                print(i)
            return 1 if any(i.severity == "error" for i in issues) else 0
        rep = run(ir, a.out, _src(a.source), vlm_of(a.vlm), not a.no_ocr)
        Path(a.out).mkdir(parents=True, exist_ok=True)
        (Path(a.out) / "report.json").write_text(json.dumps(rep.to_dict(), indent=2, default=str))
    print(f"verdict: {rep.verdict} (iterations: {rep.iterations})")
    for i in rep.issues:
        print(" ", i)
    if rep.rendered:
        print("image:", rep.rendered.png)
    return 0 if rep.verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
