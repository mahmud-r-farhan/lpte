"""Check confusion-matrix math and labelled-file validation separately from model tuning."""

import json

import pytest

from lpte.eval import EvalReport, evaluate, load_cases, overall
from lpte.languages import EnglishProfile


def test_precision_recall_f1_and_examples():
    cases = [("damn", True), ("go die", True), ("hello", False),
             ("no one likes you, go away", True), ("fuck", False)]
    report = evaluate(EnglishProfile, cases)
    assert (report.true_positives, report.false_positives,
            report.true_negatives, report.false_negatives) == (2, 1, 1, 1)
    assert report.total == 5
    assert report.accuracy == 3 / 5
    assert report.precision == 2 / 3
    assert report.recall == 2 / 3
    assert report.f1 == 2 / 3
    assert report.false_positive_examples == ["fuck"]
    assert report.false_negative_examples == ["no one likes you, go away"]


def test_overall_uses_confusion_totals_not_mean_of_language_f1s():
    first = EvalReport("a", true_positives=1, false_positives=1)
    second = EvalReport("b", true_positives=3, false_negatives=1)
    combined = overall({"a": first, "b": second})
    assert combined.total == 6
    assert combined.precision == 4 / 5
    assert combined.recall == 4 / 5
    assert combined.f1 == 4 / 5
    assert EvalReport("empty").f1 == 0.0


def test_custom_jsonl_cases_and_errors(tmp_path):
    file = tmp_path / "eval.jsonl"
    file.write_text(json.dumps({"text": "damn", "toxic": True}) + "\n\n")
    assert load_cases(file) == [("damn", True)]
    for bad in ("not json", '{"text":"x","toxic":1}', '{"text":"","toxic":true}'):
        file.write_text(bad + "\n")
        with pytest.raises(ValueError, match="eval.jsonl:1"):
            load_cases(file)
    file.write_text("\n")
    with pytest.raises(ValueError, match="no labelled cases"):
        load_cases(file)
