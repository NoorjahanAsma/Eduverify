from pathlib import Path
from eduverify import load_ir, run
from eduverify.verify import rules

EX = Path(__file__).parent.parent / "examples"


def test_chart_passes_with_source(tmp_path):
    ir = load_ir((EX / "chart.json").read_text())
    rep = run(ir, tmp_path, (EX / "source.txt").read_text(), ocr=False)
    assert rep.verdict == "pass" and rep.rendered.png.exists() and rep.rendered.svg.exists()


def test_invented_value_is_caught():
    ir = load_ir((EX / "chart.json").read_text())
    ir.series[0].values[0] = 90.0
    codes = [i.code for i in rules.check(ir, (EX / "source.txt").read_text())]
    assert "value_not_in_source" in codes


def test_length_mismatch_abstains(tmp_path):
    ir = load_ir((EX / "chart.json").read_text())
    ir.series[0].values.append(3.0)
    assert run(ir, tmp_path, ocr=False).verdict == "abstain"


def test_diagram_dangling_edge():
    ir = load_ir((EX / "diagram.json").read_text())
    ir.edges[0].dst = "zzz"
    assert "dangling_edge" in [i.code for i in rules.check(ir)]


def test_diagram_renders(tmp_path):
    rep = run(load_ir((EX / "diagram.json").read_text()), tmp_path, ocr=False)
    assert rep.verdict == "pass"


def test_relational_source_flags_missing_and_unsupported_edges():
    from eduverify import load_ir
    src = "Labels: Egg; Larva; Pupa; Adult\nEgg is followed by Larva. Larva is followed by Pupa. Pupa is followed by Adult. Adult is followed by Egg."
    ir = load_ir({"kind": "diagram", "title": "t", "nodes": [{"id": i, "label": i} for i in ["Egg", "Larva", "Pupa", "Adult"]],
                  "edges": [{"src": "Egg", "dst": "Larva"}, {"src": "Larva", "dst": "Pupa"}, {"src": "Pupa", "dst": "Adult"}]})
    codes = [i.code for i in rules.check(ir, src)]
    assert codes == ["relation_missing"]
    ir.edges.append(type(ir.edges[0])(src="Adult", dst="Egg")); ir.edges.append(type(ir.edges[0])(src="Egg", dst="Pupa"))
    assert [i.code for i in rules.check(ir, src)] == ["edge_unsupported"]


def test_thin_source_does_not_trigger_relation_rules():
    from eduverify import load_ir
    ir = load_ir({"kind": "diagram", "title": "t", "nodes": [{"id": i, "label": i} for i in ["A", "B"]], "edges": [{"src": "A", "dst": "B"}]})
    assert rules.check(ir, "Labels: A; B") == []


def test_absent_category_is_flagged():
    ir = load_ir((EX / "chart.json").read_text())
    ir.categories.append("Lakes"); ir.series[0].values.append(1.7)
    assert "category_not_in_source" in [i.code for i in rules.check(ir, (EX / "source.txt").read_text())]


def test_entailment_flags_reversed_arrow():
    from eduverify import load_ir
    from eduverify.verify import entail

    class Judge:
        calls = []
        def chat(self, prompt, images=None, system=None, json_mode=False):
            # a stub judge that knows: tail must be the food (second item in "X eats Y")
            return '{"answer": "%s"}' % ("yes" if 'from "Grass" to "Mouse"' in prompt else "no")
    ir = load_ir({"kind": "diagram", "title": "t", "nodes": [{"id": "g", "label": "Grass"}, {"id": "m", "label": "Mouse"}],
                  "edges": [{"src": "m", "dst": "g"}]})
    iss = entail.check_edges(ir, "Mouse eats Grass.", "Draw it. Each arrow points from the food to the eater.", Judge())
    assert [i.code for i in iss] == ["edge_direction"]


def test_swapped_values_between_rows_are_caught():
    src = "| Item | Share |\n|---|---|\n| Alpha | 60 |\n| Beta | 40 |"
    ir = load_ir({"kind": "chart", "chart_type": "bar", "title": "t", "categories": ["Alpha", "Beta"],
                  "series": [{"name": "Share", "values": [40, 60]}], "y_label": "Share"})
    codes = [i.code for i in rules.check(ir, src)]
    assert codes.count("value_in_wrong_row") == 2 and "value_not_in_source" not in codes


def test_long_labels_do_not_overlap(tmp_path):
    ir = load_ir({"kind": "chart", "chart_type": "bar", "title": "t", "y_label": "v",
                  "categories": ["Exclusively from ads", "Ads and subscriptions (current solution)", "Directly from national budget", "Exclusively from subscriptions", "No opinion"],
                  "series": [{"name": "s", "values": [40.1, 29.9, 13.3, 10.2, 6.5]}]})
    from eduverify.render.chart import _overlap
    import matplotlib.pyplot as plt
    rep = run(ir, tmp_path, ocr=False)
    assert rep.verdict == "pass"


def test_cli_render_pass_and_abstain(tmp_path):
    import subprocess, sys
    ok = subprocess.run([sys.executable, "-m", "eduverify.cli", "render", "examples/chart.json", "-o", str(tmp_path / "a"), "--no-ocr"], capture_output=True, text=True)
    assert ok.returncode == 0 and "verdict: pass" in ok.stdout
    assert (tmp_path / "a" / "visual.png").exists() and (tmp_path / "a" / "visual.svg").exists()
    bad = subprocess.run([sys.executable, "-m", "eduverify.cli", "render", "examples/diagram.json", "--source", "examples/source.txt", "-o", str(tmp_path / "b"), "--no-ocr"], capture_output=True, text=True)
    assert bad.returncode == 1 and "verdict: abstain" in bad.stdout and not (tmp_path / "b" / "visual.png").exists()


def test_ocr_reads_boxed_diagram_labels(tmp_path):
    import shutil
    import pytest
    if not shutil.which("tesseract"):
        pytest.skip("tesseract not installed")
    from eduverify.ir import load_ir
    from eduverify.render import render
    from eduverify.verify import readback
    ir = load_ir(open("examples/diagram.json").read())
    rd = render(ir, tmp_path)
    assert readback.ocr_check(rd.png, rd.expected_text) == []
