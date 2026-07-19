<?php
/**
 * LPTE — PHP wrapper for the Local Profanity & Toxicity Engine.
 *
 * Communicates with the Python engine via JSON IPC over proc_open().
 * User input is NEVER interpolated into Python code.
 *
 * Usage:
 *   $engine = new \Lpte\Engine('en');
 *   $result = $engine->analyze('some text');
 *   if ($result['is_toxic']) {
 *       echo "Toxic: {$result['severity']}\n";
 *   }
 */

namespace Lpte;

class Engine
{
    private string $languageCode;
    private float $threshold;
    private string $pythonPath;
    private $process;
    private $pipes;

    public function __construct(string $languageCode = 'en', float $threshold = 0.6, string $pythonPath = 'python3')
    {
        $this->languageCode = $languageCode;
        $this->threshold = $threshold;
        $this->pythonPath = $pythonPath;
        $this->startProcess();
    }

    private function startProcess(): void
    {
        $bridgeScript = $this->getBridgeScript();

        $descriptors = [
            0 => ['pipe', 'r'],  // stdin
            1 => ['pipe', 'w'],  // stdout
            2 => ['pipe', 'w'],  // stderr
        ];

        $this->process = proc_open(
            "{$this->pythonPath} -u -c " . escapeshellarg($bridgeScript),
            $descriptors,
            $this->pipes
        );

        if (!is_resource($this->process)) {
            throw new \RuntimeException('Failed to start Python engine');
        }
    }

    /**
     * Analyze text for toxic content.
     *
     * @return array{is_toxic: bool, severity: string, confidence: float, matched_terms: string[]}
     */
    public function analyze(string $text, ?float $threshold = null): array
    {
        $t = $threshold ?? $this->threshold;

        $request = json_encode([
            'command' => 'analyze',
            'text' => $text,
            'language_code' => $this->languageCode,
            'threshold' => $t,
        ]);

        fwrite($this->pipes[0], $request . "\n");
        fflush($this->pipes[0]);

        $response = fgets($this->pipes[1]);
        $result = json_decode(trim($response), true);

        return $result ?? [
            'is_toxic' => false,
            'severity' => 'NONE',
            'confidence' => 0.0,
            'matched_terms' => [],
        ];
    }

    /**
     * Quick toxicity check.
     */
    public function isToxic(string $text, ?float $threshold = null): bool
    {
        $result = $this->analyze($text, $threshold);
        return $result['is_toxic'] ?? false;
    }

    /**
     * Sanitize text by masking toxic segments.
     */
    public function sanitize(string $text, string $mask = '*'): string
    {
        $request = json_encode([
            'command' => 'sanitize',
            'text' => $text,
            'language_code' => $this->languageCode,
            'mask' => $mask,
        ]);

        fwrite($this->pipes[0], $request . "\n");
        fflush($this->pipes[0]);

        $response = fgets($this->pipes[1]);
        $result = json_decode(trim($response), true);

        return $result['sanitized'] ?? $text;
    }

    public function __destruct()
    {
        if (is_resource($this->pipes[0])) fclose($this->pipes[0]);
        if (is_resource($this->pipes[1])) fclose($this->pipes[1]);
        if (is_resource($this->pipes[2])) fclose($this->pipes[2]);
        if (is_resource($this->process)) proc_close($this->process);
    }

    private function getBridgeScript(): string
    {
        return <<<'PYTHON'
import sys, json
from lpte.core.engine import LpteEngine

engines = {}

def get_engine(lang_code):
    if lang_code not in engines:
        if lang_code == "bn":
            from lpte.languages.bn import BengaliProfile
            engines[lang_code] = LpteEngine(BengaliProfile)
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
                "severity": result.severity.name,
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
PYTHON;
    }
}
