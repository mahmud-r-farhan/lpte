"""
LPTE Web Demo — FastAPI backend serving the toxicity engine.

Run: python website/app.py
Visit: http://localhost:8000
"""

import sys
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

# Add project root to path so we can import lpte
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from lpte.core.engine import LpteEngine
from lpte.core.classifier import Severity
from lpte.languages.en import EnglishProfile
from lpte.languages.bn import BengaliProfile

# Initialize engines
engines = {
    "en": LpteEngine(EnglishProfile),
    "bn": LpteEngine(BengaliProfile),
}

app = FastAPI(
    title="LPTE — Local Profanity & Toxicity Engine",
    description="Zero-cost, on-device text toxicity analysis demo",
    version="1.0.0",
)


class AnalyzeRequest(BaseModel):
    text: str
    language: str = "en"
    threshold: float = 0.6


class AnalyzeResponse(BaseModel):
    is_toxic: bool
    severity: str
    confidence: float
    matched_terms: list[str]
    sanitized: str
    signals: dict[str, int]


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    if req.text.strip() == "":
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    engine = engines.get(req.language, engines["en"])
    result = engine.analyze(req.text, req.threshold)
    sanitized = engine.sanitize(req.text) if result.is_toxic else req.text

    return AnalyzeResponse(
        is_toxic=result.is_toxic,
        severity=result.severity.name,
        confidence=round(result.confidence, 3),
        matched_terms=result.matched_terms,
        sanitized=sanitized,
        signals=result.signals,
    )


@app.get("/api/languages")
def list_languages():
    return {
        "languages": [
            {"code": "en", "name": "English", "native": "English"},
            {"code": "bn", "name": "Bengali", "native": "বাংলা"},
        ]
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# Serve static files (React frontend)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def serve_frontend():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "LPTE API is running. Frontend not built yet. Visit /docs for API docs."}


if __name__ == "__main__":
    import uvicorn
    print("\n  LPTE Web Demo")
    print("  http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
