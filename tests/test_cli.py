"""Subprocess tests exercise the installed-style CLI, not only function calls."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def invoke():
    def run(*args, input=None):
        return subprocess.run(
            [sys.executable, "-m", "lpte", *args],
            input=input, text=True, capture_output=True, check=False,
        )
    return run


def test_analyze_json_and_policy(invoke):
    proc = invoke("analyze", "damn this is good", "--policy", "balanced", "--sanitize", "--json")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["categories"] == ["profanity"]
    assert data["decision"]["action"] == "MASK"
    assert data["sanitized"] == "**** this is good"
    assert "latency_ms" in data


def test_code_switched_and_custom_mask(invoke):
    proc = invoke("analyze", "তুই একদম idiot", "--lang", "bn+en", "--json")
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["matched_terms"] == ["idiot"]
    proc = invoke("sanitize", "f4ck this bullsh1t", "--mask", "#")
    assert proc.stdout.strip() == "#### this ########"


def test_batch_streams_file_and_stdin_as_valid_json(invoke, tmp_path):
    path = tmp_path / "messages.txt"
    path.write_text("hello\n\n you nigger\nf4ck\n", encoding="utf-8")
    for file, input in ((str(path), None), ("-", path.read_text())):
        proc = invoke("batch", file, "--policy", "balanced", "--json", input=input)
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data["total"] == 3 and data["toxic_count"] == 2
        assert [r["text"] for r in data["results"]] == ["hello", " you nigger", "f4ck"]
        assert data["results"][1]["decision"]["action"] == "BLOCK"
    assert invoke("batch", str(tmp_path / "missing.txt")).returncode == 2
    empty = tmp_path / "empty.txt"
    empty.write_text(" \n\n")
    assert invoke("batch", str(empty), "--json").returncode == 2


def test_validate_file_directory_and_invalid(invoke, tmp_path):
    good = Path(__file__).parent.parent / "languages" / "en_profile.json"
    assert "VALID" in invoke("validate", str(good)).stdout
    directory = invoke("validate", str(good.parent))
    assert directory.returncode == 0 and directory.stdout.count("VALID") == 11
    bad = tmp_path / "xx_profile.json"
    bad.write_text('{"language_code": "xx", "bad_words": ["word"]}')
    invalid = invoke("validate", str(bad))
    assert invalid.returncode == 1 and "language_name" in invalid.stdout


def test_pack_scaffold_custom_language_and_override(invoke, tmp_path):
    new = invoke("init-pack", "xx", "--name", "Test", "--word", "vulgar",
                 "--category", "insult", "--scripts", "Latin", "--output", str(tmp_path))
    assert new.returncode == 0, new.stderr
    path = tmp_path / "xx_profile.json"
    assert json.loads(path.read_text())["word_categories"] == {"vulgar": "insult"}
    assert invoke("validate", str(path)).returncode == 0
    assert invoke("init-pack", "xx", "--name", "Test", "--word", "vulgar",
                  "--output", str(tmp_path)).returncode == 2  # no clobber
    proc = invoke("analyze", "vulgar", "--lang", "xx", "--packs-dir", str(tmp_path), "--json")
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["categories"] == ["insult"]
    listed = json.loads(invoke("languages", "--packs-dir", str(tmp_path), "--json").stdout)
    assert "xx" in [p["code"] for p in listed["languages"]]
    # Explicit same-code directory replaces the built-in; implicit repo JSON
    # duplicates do not replace built-in native stemmers.
    override = tmp_path / "en_profile.json"
    override.write_text(json.dumps({"language_code": "en", "language_name": "Custom",
                                    "bad_words": ["vulgar"]}))
    data = json.loads(invoke("analyze", "vulgar", "--lang", "en", "--packs-dir",
                             str(tmp_path), "--json").stdout)
    assert data["is_toxic"] and data["language"] == "en"


def test_eval_custom_cases_and_fail_under(invoke, tmp_path):
    corpus = tmp_path / "cases.jsonl"
    corpus.write_text('\n'.join(json.dumps(d) for d in (
        {"text": "hello", "toxic": False},
        {"text": "damn", "toxic": True},
        {"text": "nothing good here", "toxic": True},
    )) + "\n")
    proc = invoke("eval", "--lang", "en", "--cases", str(corpus), "--verbose")
    assert proc.returncode == 0 and "False negatives" in proc.stdout
    assert "0.667" in proc.stdout  # 2TP / (2TP + 0FP + 1FN)
    proc = invoke("eval", "--lang", "en", "--cases", str(corpus), "--fail-under", "0.9")
    assert proc.returncode == 1 and "FAIL" in proc.stdout
    assert invoke("eval", "--fail-under", "0.9").returncode == 0
    assert invoke("eval", "--cases", str(corpus)).returncode == 2


@pytest.mark.parametrize("args", [
    ("analyze", "hello", "--threshold", "nan"),
    ("analyze", "hello", "--lang", "unknown"),
    ("analyze", "hello", "--threshold", "1.1"),
    ("sanitize", "hello", "--mask", "**"),
    ("bench", "--iterations", "0"),
    ("init-pack", "../oops", "--name", "Oops", "--word", "word"),
])
def test_bad_input_returns_error_not_traceback(invoke, args):
    proc = invoke(*args)
    assert proc.returncode != 0
    assert "Traceback" not in proc.stderr


def test_benchmark_reports_cache_mode(invoke):
    proc = invoke("bench", "--iterations", "1")
    assert proc.returncode == 0, proc.stderr
    assert "cache disabled" in proc.stdout and "throughput" in proc.stdout
