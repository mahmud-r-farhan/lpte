"""Optional FastAPI demo. Unlike the Python core, this is an HTTP service.

The demo's browser sends text to this server (same-origin /api/*). Host it on
infrastructure you control for private content; the engine itself has no egress.
Run: python website/app.py
"""

from __future__ import annotations

import os
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from lpte import Action, LpteEngine, MultiLangEngine, __version__, get_policy  # noqa: E402
from lpte.registry import available_languages  # noqa: E402

# Local bundled JSON packs only ADD codes; explicit LPTE_PACKS_DIR also permits
# community overrides of built-in rules. Invalid JSON fails startup loudly.
extra = os.environ.get("LPTE_PACKS_DIR")
local_packs = Path(__file__).parent.parent / "languages"
profiles = available_languages(
    extra or (local_packs if local_packs.is_dir() else None), override=bool(extra)
)
engines = {code: LpteEngine(p, cache_size=512) for code, p in profiles.items()}

app = FastAPI(title="LPTE — Local Profanity & Toxicity Engine", version=__version__)
# No wildcard CORS: the bundled browser UI and API are on the same origin.

MAX_TEXT_LENGTH = 2000
MAX_BATCH_SIZE = 50
PolicyName = Literal["strict", "balanced", "lenient"]


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    language: str = Field("en", max_length=64)
    threshold: float = Field(0.6, ge=0.0, le=1.0, allow_inf_nan=False)
    policy: PolicyName | None = None

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, text: str) -> str:
        if not text.strip():
            raise ValueError("Text must not be blank")
        return text


class BatchAnalyzeRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=MAX_BATCH_SIZE)
    language: str = Field("en", max_length=64)
    threshold: float = Field(0.6, ge=0.0, le=1.0, allow_inf_nan=False)
    policy: PolicyName | None = None

    @field_validator("texts")
    @classmethod
    def check_texts(cls, texts: list[str]) -> list[str]:
        if any(not t.strip() or len(t) > MAX_TEXT_LENGTH for t in texts):
            raise ValueError(f"Each text must contain 1-{MAX_TEXT_LENGTH} characters")
        return texts


class AnalyzeResponse(BaseModel):
    is_toxic: bool
    severity: str
    confidence: float
    matched_terms: list[str]
    categories: list[str]
    language: str
    sanitized: str
    signals: dict[str, int]
    decision: dict[str, object] | None = None
    latency_ms: float | None = None


class BatchAnalyzeResponse(BaseModel):
    results: list[AnalyzeResponse]
    total: int
    toxic_count: int
    latency_ms: float


@lru_cache(maxsize=16)
def _multi(codes: tuple[str, ...]) -> MultiLangEngine:
    return MultiLangEngine([profiles[c] for c in codes], cache_size=256)


def _get_engine(language: str) -> LpteEngine | MultiLangEngine:
    if language in engines:
        return engines[language]
    if language in ("auto", "all", "*"):
        return _multi(tuple(profiles))
    codes = tuple(language.replace(",", "+").split("+"))
    if (
        not 2 <= len(codes) <= 3
        or len(set(codes)) != len(codes)
        or any(c not in profiles for c in codes)
    ):
        raise HTTPException(
            status_code=400, detail="Unknown language; see /api/languages or use a valid pair"
        )
    return _multi(codes)


def _build_response(
    engine: LpteEngine | MultiLangEngine,
    text: str,
    threshold: float,
    policy: PolicyName | None,
) -> AnalyzeResponse:
    result = engine.analyze(text, threshold)
    decision = get_policy(policy).decide(result, text) if policy else None
    # With a policy, display the masked version only if publishing it is the
    # chosen action. Without one, preserve the demo's old preview behavior.
    mask = decision.action == Action.MASK if decision else result.is_toxic
    # A policy's category threshold may be lower than the caller's binary
    # threshold; still mask when the policy explicitly chooses MASK.
    mask_threshold = threshold if result.is_toxic else result.confidence
    sanitized = engine.sanitize(text, threshold=mask_threshold) if mask else text
    return AnalyzeResponse(
        is_toxic=result.is_toxic,
        severity=result.severity.name,
        confidence=round(result.confidence, 4),
        matched_terms=result.matched_terms,
        categories=result.categories,
        language=result.language,
        sanitized=sanitized,
        signals=result.signals,
        decision=decision.as_dict() if decision else None,
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    engine = _get_engine(req.language)
    start = time.perf_counter()
    response = _build_response(engine, req.text, req.threshold, req.policy)
    response.latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return response


@app.post("/api/batch", response_model=BatchAnalyzeResponse)
def batch_analyze(req: BatchAnalyzeRequest):
    engine = _get_engine(req.language)
    start = time.perf_counter()
    responses = [_build_response(engine, text, req.threshold, req.policy) for text in req.texts]
    return BatchAnalyzeResponse(
        results=responses,
        total=len(responses),
        toxic_count=sum(int(r.is_toxic) for r in responses),
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
    )


@app.get("/api/languages")
def list_languages():
    return {
        "languages": [
            {
                "code": code,
                "name": p.language_name,
                "vocabulary_size": len(p.bad_words),
                "version": p.version,
                "description": p.description,
            }
            for code, p in sorted(profiles.items())
        ]
    }


@app.get("/api/stats")
def get_stats():
    return {"engines": {code: engine.engine_stats() for code, engine in engines.items()}}


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__, "engines": list(engines)}


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def serve_frontend():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": f"LPTE API v{__version__}. Frontend not found; visit /docs."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
