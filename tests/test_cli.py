"""Tests for the lpte command-line interface."""

import json

import pytest

from lpte.cli import build_parser, main


@pytest.fixture
def capsys_out(capsys):
    def run(argv):
        code = main(argv)
        return code, capsys.readouterr().out
    return run


class TestLanguagesCommand:
    def test_lists_builtin_packs(self, capsys_out):
        code, out = capsys_out(["languages"])
        assert code == 0
        assert "en" in out and "bn" in out

    def test_json_output(self, capsys_out):
        code, out = capsys_out(["languages", "--json"])
        assert code == 0
        data = json.loads(out)
        codes = {l["code"] for l in data["languages"]}
        assert {"en", "bn", "zh"} <= codes


class TestAnalyzeCommand:
    def test_detects_toxicity(self, capsys_out):
        code, out = capsys_out(["analyze", "you are a fucking idiot"])
        assert code == 0
        assert "TOXIC" in out
        assert "fuck" in out

    def test_clean_text(self, capsys_out):
        code, out = capsys_out(["analyze", "hello how are you today"])
        assert code == 0
        assert "CLEAN" in out

    def test_json_output(self, capsys_out):
        code, out = capsys_out(["analyze", "you are a fucking idiot", "--json"])
        data = json.loads(out)
        assert data["is_toxic"] is True
        assert data["confidence"] > 0
        assert "categories" in data

    def test_policy_applied(self, capsys_out):
        code, out = capsys_out(
            ["analyze", "you are a fucking idiot", "--policy", "balanced"])
        assert "MASK" in out or "BLOCK" in out

    def test_sanitize_flag(self, capsys_out):
        # The header echoes the raw input; the "sanitized:" line must be masked.
        code, out = capsys_out(["analyze", "f4ck this", "--sanitize"])
        sanitized_line = [ln for ln in out.splitlines() if "sanitized" in ln]
        assert sanitized_line, out
        assert "f4ck" not in sanitized_line[0]
        assert "****" in sanitized_line[0]

    def test_unknown_language_exits(self, capsys_out):
        with pytest.raises(SystemExit):
            main(["analyze", "hello", "--lang", "xx"])

    def test_multilang_spec(self, capsys_out):
        code, out = capsys_out(["analyze", "তুই একদম idiot", "--lang", "bn+en"])
        assert code == 0
        assert "TOXIC" in out


class TestSanitizeCommand:
    def test_masks_text(self, capsys_out):
        code, out = capsys_out(["sanitize", "you are a bastard"])
        assert code == 0
        assert "bastard" not in out
        assert "*******" in out

    def test_custom_mask(self, capsys_out):
        code, out = capsys_out(["sanitize", "you are a bastard", "--mask", "#"])
        assert "#######" in out


class TestBatchCommand:
    def test_processes_file(self, capsys_out, tmp_path):
        f = tmp_path / "msgs.txt"
        f.write_text("hello world\nyou are an idiot\nnice day\n", encoding="utf-8")
        code, out = capsys_out(["batch", str(f)])
        assert code == 0
        assert "1/3 toxic" in out

    def test_json_output(self, capsys_out, tmp_path):
        f = tmp_path / "msgs.txt"
        f.write_text("you idiot\nall good here\n", encoding="utf-8")
        code, out = capsys_out(["batch", str(f), "--json"])
        data = json.loads(out)
        assert data["total"] == 2
        assert data["toxic_count"] == 1

    def test_missing_file_exits(self, capsys_out):
        with pytest.raises(SystemExit):
            main(["batch", "/nonexistent/file.txt"])


class TestValidateCommand:
    def test_valid_pack(self, capsys_out):
        code, out = capsys_out(["validate", "languages/bn_profile.json"])
        assert code == 0
        assert "VALID" in out

    def test_invalid_pack(self, capsys_out, tmp_path):
        bad = tmp_path / "bad_profile.json"
        bad.write_text('{"language_name": "No code"}', encoding="utf-8")
        code, out = capsys_out(["validate", str(bad)])
        assert code == 1
        assert "INVALID" in out


class TestBenchCommand:
    def test_runs(self, capsys_out):
        code, out = capsys_out(["bench", "--iterations", "5"])
        assert code == 0
        assert "throughput" in out
        assert "p95" in out


class TestParser:
    def test_command_is_required(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])
