"""
Tests for LanguageRegistry and dynamic language pack registration.
"""

import json
import tempfile
from pathlib import Path

import pytest

from lpte import LpteEngine, LanguageRegistry
from lpte.cli import build_parser
from lpte.core.registry import default_registry


class TestLanguageRegistry:
    def test_loads_builtins(self):
        registry = LanguageRegistry()
        profiles = registry.get_all_profiles()
        assert "en" in profiles
        assert "bn" in profiles
        assert "zh" in profiles

    def test_register_dict(self):
        registry = LanguageRegistry()
        pack = {
            "language_code": "it_test",
            "language_name": "Italian Test",
            "bad_words": ["stronzo", "cazzo"],
            "suffix_rules": ["zione", "mente"],
            "word_categories": {"stronzo": "insult"},
            "version": "1.0.0",
        }
        profile = registry.register_dict(pack, persist=False)
        assert profile.language_code == "it_test"
        assert profile.language_name == "Italian Test"
        assert "stronzo" in profile.bad_words

        # Verify engine creation
        engine = LpteEngine(profile)
        res = engine.analyze("tu sei uno stronzo")
        assert res.is_toxic is True
        assert "stronzo" in res.matched_terms

    def test_export_json_and_dict(self):
        registry = LanguageRegistry()
        prof = registry.get_profile("en")
        d = registry.to_dict(prof)
        assert d["language_code"] == "en"
        assert "fuck" in d["bad_words"]

        json_str = registry.export_json("en")
        parsed = json.loads(json_str)
        assert parsed["language_code"] == "en"

    def test_remove_profile(self):
        registry = LanguageRegistry()
        pack = {
            "language_code": "remove_me",
            "language_name": "Remove Test",
            "bad_words": ["badword"],
        }
        registry.register_dict(pack, persist=False)
        assert registry.get_profile("remove_me") is not None

        removed = registry.remove_profile("remove_me")
        assert removed is True
        assert registry.get_profile("remove_me") is None

    def test_get_schema(self):
        schema = LanguageRegistry.get_schema()
        assert schema["title"] == "LPTE Language Pack Schema"
        assert "language_code" in schema["properties"]
        assert "bad_words" in schema["properties"]

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = LanguageRegistry(languages_dir=tmpdir)
            pack = {
                "language_code": "persisted_lang",
                "language_name": "Persisted Language",
                "bad_words": ["bad1", "bad2"],
            }
            registry.register_dict(pack, persist=True)

            file_path = Path(tmpdir) / "persisted_lang_profile.json"
            assert file_path.exists()

            # Load new registry pointing to same dir
            new_registry = LanguageRegistry(languages_dir=tmpdir)
            assert new_registry.get_profile("persisted_lang") is not None


class TestCliAddLanguage:
    def test_cli_add_language_json_string(self):
        parser = build_parser()
        pack_json = json.dumps({
            "language_code": "cli_test",
            "language_name": "CLI Test",
            "bad_words": ["clitestword"],
        })
        args = parser.parse_args(["add-language", pack_json, "--json"])
        assert args.command == "add-language"

        from lpte.cli import cmd_add_language
        ret = cmd_add_language(args)
        assert ret == 0
        assert default_registry.get_profile("cli_test") is not None


class TestApiLanguageEndpoints:
    def test_api_languages_endpoints(self):
        try:
            from fastapi.testclient import TestClient
            from website.app import app
        except ImportError:
            pytest.skip("FastAPI / TestClient dependencies not available")

        client = TestClient(app)

        # 1. Get schema
        res = client.get("/api/languages/schema")
        assert res.status_code == 200
        assert "properties" in res.json()

        # 2. Add language
        pack = {
            "language_code": "api_test",
            "language_name": "API Test",
            "bad_words": ["apitestword"],
            "persist": False,
        }
        res_add = client.post("/api/languages", json=pack)
        assert res_add.status_code == 200
        assert res_add.json()["status"] == "success"

        # 3. Analyze text in new language
        res_an = client.post("/api/analyze", json={"text": "this has apitestword in it", "language": "api_test"})
        assert res_an.status_code == 200
        assert res_an.json()["is_toxic"] is True

        # 4. Remove language
        res_del = client.delete("/api/languages/api_test")
        assert res_del.status_code == 200
