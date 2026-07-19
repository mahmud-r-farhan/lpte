<?php
/**
 * LPTE — PHP wrapper for the Local Profanity & Toxicity Engine.
 *
 * Communicates with the Python LPTE engine via proc_open() subprocess IPC.
 *
 * Usage:
 *   $engine = new LpteEngine('en');
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

    public function __construct(string $languageCode = 'en', float $threshold = 0.6, string $pythonPath = 'python3')
    {
        $this->languageCode = $languageCode;
        $this->threshold = $threshold;
        $this->pythonPath = $pythonPath;
    }

    /**
     * Analyze text for toxic content.
     *
     * @param string $text Input text
     * @param float|null $threshold Classification threshold (0.0-1.0)
     * @return array{is_toxic: bool, severity: string, confidence: float, matched_terms: string[]}
     */
    public function analyze(string $text, ?float $threshold = null): array
    {
        $t = $threshold ?? $this->threshold;
        $escapedText = addslashes($text);

        $script = <<<PYTHON
import sys, json
sys.path.insert(0, '.')
from lpte import LpteEngine
from lpte.languages import EnglishProfile, BengaliProfile

profiles = {'en': EnglishProfile, 'bn': BengaliProfile}
profile = profiles.get('{$this->languageCode}', EnglishProfile)
engine = LpteEngine(profile)

result = engine.analyze("""{$escapedText}""", {$t})
print(json.dumps({
    'is_toxic': result.is_toxic,
    'severity': result.severity.name,
    'confidence': result.confidence,
    'matched_terms': result.matched_terms
}))
PYTHON;

        $output = $this->runPython($script);
        return json_decode($output, true) ?? [
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
        $escapedText = addslashes($text);
        $escapedMask = addslashes($mask);

        $script = <<<PYTHON
import sys, json
sys.path.insert(0, '.')
from lpte import LpteEngine
from lpte.languages import EnglishProfile

engine = LpteEngine(EnglishProfile)
result = engine.sanitize("""{$escapedText}""", "{$escapedMask}")
print(json.dumps({'result': result}))
PYTHON;

        $output = $this->runPython($script);
        $decoded = json_decode($output, true);
        return $decoded['result'] ?? $text;
    }

    private function runPython(string $script): string
    {
        $descriptors = [
            0 => ['pipe', 'r'],  // stdin
            1 => ['pipe', 'w'],  // stdout
            2 => ['pipe', 'w'],  // stderr
        ];

        $process = proc_open(
            "{$this->pythonPath} -c " . escapeshellarg($script),
            $descriptors,
            $pipes
        );

        if (!is_resource($process)) {
            throw new \RuntimeException('Failed to start Python process');
        }

        fclose($pipes[0]);
        $output = stream_get_contents($pipes[1]);
        fclose($pipes[1]);
        fclose($pipes[2]);

        $exitCode = proc_close($process);
        if ($exitCode !== 0) {
            throw new \RuntimeException("Python process failed with exit code {$exitCode}");
        }

        return trim($output);
    }
}
