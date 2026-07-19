import sys, json
from lpte.core.engine import LpteEngine

engines = {}

def get_engine(lang_code):
    if lang_code not in engines:
        if lang_code == "bn":
            from lpte.languages.bn import BengaliProfile
            engines[lang_code] = LpteEngine(BengaliProfile)
        elif lang_code == "en":
            from lpte.languages.en import EnglishProfile
            engines[lang_code] = LpteEngine(EnglishProfile)
        else:
            from lpte.languages.en import EnglishProfile
            engines[lang_code] = LpteEngine(EnglishProfile)
    return engines[lang_code]

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
        engine = get_engine(req.get("language_code", "en"))
        cmd = req.get("command", "analyze")

        if cmd == "analyze":
            result = engine.analyze(req["text"], req.get("threshold", 0.6))
            resp = {
                "is_toxic": result.is_toxic,
                "severity": result.severity.value,
                "confidence": result.confidence,
                "matched_terms": result.matched_terms,
            }
        elif cmd == "sanitize":
            sanitized = engine.sanitize(req["text"], req.get("mask", "*"))
            resp = {"sanitized": sanitized}
        else:
            resp = {"error": f"unknown command: {cmd}"}

        print(json.dumps(resp), flush=True)
    except Exception as e:
        print(json.dumps({"error": str(e)}), flush=True)
