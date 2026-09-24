"""Shared built-in and JSON language-pack registry for CLI and integrations."""

from __future__ import annotations

from pathlib import Path

from lpte.core.loader import LanguagePackLoader
from lpte.core.profile import LanguageProfile


def builtin_profiles() -> dict[str, LanguageProfile]:
    from lpte.languages import (
        ArabicProfile,
        BengaliProfile,
        ChineseProfile,
        EnglishProfile,
        FrenchProfile,
        GermanProfile,
        HindiProfile,
        JapaneseProfile,
        KoreanProfile,
        RussianProfile,
        SpanishProfile,
    )

    profiles = (
        EnglishProfile,
        BengaliProfile,
        ChineseProfile,
        JapaneseProfile,
        KoreanProfile,
        RussianProfile,
        SpanishProfile,
        HindiProfile,
        FrenchProfile,
        GermanProfile,
        ArabicProfile,
    )
    return {p.language_code: p for p in profiles}


def available_languages(
    packs_dir: str | Path | None = None,
    *,
    override: bool = False,
) -> dict[str, LanguageProfile]:
    """Built-ins plus optional validated JSON packs.

    Bundled JSON files in ``./languages`` do not replace the native stemmers.
    An *explicit* packs_dir can override existing codes (for community-specific
    rules) or add brand-new languages. No exceptions are swallowed.
    """
    profiles = builtin_profiles()
    if packs_dir is not None:
        packs = LanguagePackLoader.load_directory(packs_dir)
        if override:
            profiles.update(packs)
        else:
            for code, profile in packs.items():
                profiles.setdefault(code, profile)
    return profiles
