"""
LPTE Web Demo — FastAPI backend serving the toxicity engine.

Run: python website/app.py
Visit: http://localhost:8000

The demo exposes the same API surface an integrator would use in production:
single analysis, batch analysis, sanitization, moderation-policy decisions,
pack introspection, and dynamic runtime language creation.
"""

import sys
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

# Add project root to path so we can import lpte
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from lpte.core.engine import LpteEngine
from lpte.core.classifier import Severity
from lpte.core.loader import LanguagePackLoader
from lpte.core.multilang import MultiLangEngine
from lpte.core.policy import POLICY_PRESETS, Action, ModerationPolicy, get_policy
from lpte.core.registry import LanguageRegistry, default_registry

# ─── Engine Setup ─────────────────────────────────────────────────────────────

# Initialize engines from default registry (built-ins + directory packs)
engines: dict[str, LpteEngine] = {
    code: LpteEngine(profile, cache_size=512)
    for code, profile in default_registry.get_all_profiles().items()
}

# Common code-switched pairs (e.g. Banglish "তুই একদম idiot", Hinglish).
# Kept warm so mixed-script messages are analysed in a single request.
multilang_engines: dict[str, MultiLangEngine] = {}

en_prof = default_registry.get_profile("en")
bn_prof = default_registry.get_profile("bn")
hi_prof = default_registry.get_profile("hi")

if bn_prof and en_prof:
    multilang_engines["bn+en"] = MultiLangEngine([bn_prof, en_prof], cache_size=256)
if hi_prof and en_prof:
    multilang_engines["hi+en"] = MultiLangEngine([hi_prof, en_prof], cache_size=256)

# Moderation policies available to the API
policies: dict[str, ModerationPolicy] = {
    name: get_policy(name) for name in POLICY_PRESETS
}

# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LPTE — Local Profanity & Toxicity Engine",
    description="Zero-cost, on-device text toxicity analysis demo with dynamic language extension",
    version="1.2.0",
)

# Allow all origins for local development / demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Request / Response Models ────────────────────────────────────────────────

MAX_TEXT_LENGTH = 2000
MAX_BATCH_SIZE = 50


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    language: str = "en"
    threshold: float = Field(0.6, ge=0.0, le=1.0)
    policy: Optional[str] = None

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Text must not be blank")
        return v

    @field_validator("policy")
    @classmethod
    def policy_known(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in POLICY_PRESETS:
            raise ValueError(f"Unknown policy '{v}'. Options: {sorted(POLICY_PRESETS)}")
        return v


class BatchAnalyzeRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=MAX_BATCH_SIZE)
    language: str = "en"
    threshold: float = Field(0.6, ge=0.0, le=1.0)
    policy: Optional[str] = None


class AddLanguageRequest(BaseModel):
    language_code: str = Field(..., min_length=2, max_length=10)
    language_name: str = Field(..., min_length=1, max_length=100)
    bad_words: list[str] = Field(..., min_length=1)
    suffix_rules: list[str] = Field(default_factory=list)
    word_categories: dict[str, str] = Field(default_factory=dict)
    context_rules: dict[str, list[str]] = Field(default_factory=dict)
    min_word_length: int = Field(2, ge=1)
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    persist: bool = True


class DecisionModel(BaseModel):
    action: str
    reason: str
    severity: str
    confidence: float
    categories: list[str] = []
    triggered_categories: list[str] = []
    matched_terms: list[str] = []
    language: str = ""
    should_publish: bool
    needs_review: bool


class AnalyzeResponse(BaseModel):
    is_toxic: bool
    severity: str
    confidence: float
    matched_terms: list[str]
    sanitized: str
    signals: dict[str, int]
    categories: list[str] = []
    language: str = ""
    decision: Optional[DecisionModel] = None
    latency_ms: Optional[float] = None


class BatchAnalyzeResponse(BaseModel):
    results: list[AnalyzeResponse]
    total: int
    toxic_count: int
    latency_ms: float


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_engine(language: str):
    """Resolve a language code, a 'bn+en' pair, or 'auto' to an engine."""
    key = (language or "en").strip().lower()

    if key in multilang_engines:
        return multilang_engines[key]

    if key in engines:
        return engines[key]

    # Check registry for dynamically registered single profiles
    prof = default_registry.get_profile(key)
    if prof is not None:
        engine = LpteEngine(prof, cache_size=256)
        engines[key] = engine
        return engine

    # Check for multi-language combination e.g. "it+en" or "auto"
    if "+" in key or "," in key or key in ("auto", "all", "*"):
        all_profs = default_registry.get_all_profiles()
        if key in ("auto", "all", "*"):
            return MultiLangEngine(list(all_profs.values()), cache_size=256)

        codes = [c.strip().lower() for c in key.replace(",", "+").split("+") if c.strip()]
        matched_profs = [all_profs[c] for c in codes if c in all_profs]
        if matched_profs:
            return MultiLangEngine(matched_profs, cache_size=256)

    # Default fallback to English or first available engine
    return engines.get("en") or next(iter(engines.values()))


def _build_response(engine, text: str, threshold: float, policy_name: Optional[str],
                    latency_ms: float | None = None) -> AnalyzeResponse:
    result = engine.analyze(text, threshold)
    sanitized = engine.sanitize(text, threshold=threshold) if result.is_toxic else text

    decision = None
    if policy_name:
        policy = policies.get(policy_name)
        if policy is not None:
            decision = DecisionModel(**policy.decide(result).as_dict())

    return AnalyzeResponse(
        is_toxic=result.is_toxic,
        severity=result.severity.name,
        confidence=round(result.confidence, 3),
        matched_terms=result.matched_terms,
        sanitized=sanitized,
        signals=result.signals,
        categories=list(result.categories),
        language=getattr(result, "language", "") or "",
        decision=decision,
        latency_ms=round(latency_ms, 2) if latency_ms is not None else None,
    )


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """Analyze a single text string for toxicity."""
    engine = _get_engine(req.language)
    t0 = time.perf_counter()
    response = _build_response(engine, req.text, req.threshold, req.policy)
    response.latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    return response


@app.post("/api/batch", response_model=BatchAnalyzeResponse)
def batch_analyze(req: BatchAnalyzeRequest):
    """Analyze multiple texts in one request (max 50)."""
    engine = _get_engine(req.language)
    t0 = time.perf_counter()

    responses = []
    for text in req.texts:
        text = text.strip()
        if not text:
            continue
        responses.append(_build_response(engine, text, req.threshold, req.policy))

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    toxic_count = sum(1 for r in responses if r.is_toxic)

    return BatchAnalyzeResponse(
        results=responses,
        total=len(responses),
        toxic_count=toxic_count,
        latency_ms=elapsed,
    )


@app.get("/api/languages")
def list_languages():
    """List all available language engines (built-in + dynamically registered)."""
    all_profiles = default_registry.get_all_profiles()
    langs = []
    for code, p in sorted(all_profiles.items()):
        langs.append({
            "code": code,
            "name": p.language_name,
            "vocabulary_size": len(p.bad_words),
            "version": p.version,
            "description": p.description,
            "author": getattr(p, "author", ""),
        })
    for code, ml in multilang_engines.items():
        langs.append({
            "code": code,
            "name": " + ".join(p.language_name for p in ml.profiles),
            "vocabulary_size": sum(len(p.bad_words) for p in ml.profiles),
            "version": "1.2.0",
            "description": "Code-switched / mixed-script detection",
        })
    return {"languages": langs}


@app.get("/api/languages/schema")
def get_language_schema():
    """Return standard JSON schema and metadata for dynamic language forms."""
    return LanguageRegistry.get_schema()


@app.post("/api/languages")
def add_language(req: AddLanguageRequest):
    """Dynamically register a new language pack at runtime without code changes."""
    try:
        data = req.model_dump()
        persist = data.pop("persist", True)
        profile = default_registry.register_dict(data, persist=persist)
        code = profile.language_code
        engines[code] = LpteEngine(profile, cache_size=256)
        return {
            "status": "success",
            "message": f"Language pack '{profile.language_name}' ({code}) registered successfully",
            "language": {
                "code": code,
                "name": profile.language_name,
                "vocabulary_size": len(profile.bad_words),
                "version": profile.version,
            },
            "total_languages": len(default_registry.get_all_profiles()),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to register language pack: {exc}")


@app.delete("/api/languages/{code}")
def remove_language(code: str, delete_file: bool = True):
    """Unregister and optionally delete a custom language pack."""
    code = code.strip().lower()
    core_builtins = {"en", "bn", "zh", "ja", "ko", "ru", "es", "hi", "fr", "de", "ar"}
    if code in core_builtins:
        raise HTTPException(status_code=400, detail="Cannot delete core built-in language pack")

    removed = default_registry.remove_profile(code, delete_file=delete_file)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Language code '{code}' not found")

    engines.pop(code, None)
    return {"status": "success", "message": f"Language '{code}' removed successfully"}


@app.get("/api/policies")
def list_policies():
    """List moderation policy presets and their per-category thresholds."""
    return {
        "policies": {
            name: {
                "category_thresholds": pol.category_thresholds,
                "default_threshold": pol.default_threshold,
                "mask_above": pol.mask_above,
                "block_above": pol.block_above,
                "always_block_categories": sorted(pol.always_block_categories),
            }
            for name, pol in policies.items()
        },
        "actions": [a.name for a in Action],
    }


@app.get("/api/stats")
def get_stats():
    """Return per-engine analysis statistics."""
    # Ensure all registered profiles have an engine instance for stats reporting
    for code, prof in default_registry.get_all_profiles().items():
        if code not in engines:
            engines[code] = LpteEngine(prof, cache_size=256)

    return {
        "engines": {
            code: engine.engine_stats()
            for code, engine in engines.items()
        }
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "1.2.0",
        "engines": list(engines.keys()),
        "multilang": list(multilang_engines.keys()),
        "policies": list(policies.keys()),
    }


# ─── Static Files ─────────────────────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def serve_frontend():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "LPTE API v1.2.0. Frontend not found. Visit /docs for API docs."}


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n  LPTE Web Demo v1.2.0")
    print("  http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
