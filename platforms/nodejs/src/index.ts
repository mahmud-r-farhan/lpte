/**
 * LPTE Node.js Native Module
 *
 * Provides on-device toxicity analysis for Node.js applications.
 * Spawns a Python subprocess to run the LPTE engine, or loads
 * the engine directly via child_process + JSON IPC.
 *
 * Usage:
 * ```typescript
 * import { analyze, isToxic, sanitize } from 'lpte';
 *
 * const result = await analyze('some text', { languageCode: 'en' });
 * if (result.isToxic) {
 *   console.log(`Toxic: ${result.severity}`);
 * }
 * ```
 */

import { spawn, ChildProcess } from 'child_process';
import { join } from 'path';

export interface LpteResult {
  isToxic: boolean;
  severity: 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  confidence: number;
  matchedTerms: string[];
}

export interface LpteOptions {
  languageCode?: string;
  threshold?: number;
  pythonPath?: string;
}

// Path to the Python LPTE package
const LPTE_PYTHON_DIR = join(__dirname, '..', '..', '..');

// Python bridge script — runs as a persistent subprocess
const BRIDGE_SCRIPT = `
import sys, json
from lpte.core.engine import LpteEngine
engines = {}
def get_engine(lang):
    if lang not in engines:
        if lang == "bn":
            from lpte.languages.bn import BengaliProfile
            engines[lang] = LpteEngine(BengaliProfile)
        else:
            from lpte.languages.en import EnglishProfile
            engines[lang] = LpteEngine(EnglishProfile)
    return engines[lang]
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        req = json.loads(line)
        engine = get_engine(req.get("language_code", "en"))
        cmd = req.get("command", "analyze")
        if cmd == "analyze":
            r = engine.analyze(req["text"], req.get("threshold", 0.6))
            print(json.dumps({"is_toxic": r.is_toxic, "severity": r.severity.name, "confidence": r.confidence, "matched_terms": r.matched_terms}))
        elif cmd == "sanitize":
            s = engine.sanitize(req["text"], req.get("mask", "*"))
            print(json.dumps({"sanitized": s}))
        else:
            print(json.dumps({"error": "unknown command"}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
`;

let engineProcess: ChildProcess | null = null;

/**
 * Get or create the Python engine subprocess.
 */
function getEngine(options: LpteOptions = {}): ChildProcess {
  if (engineProcess && !engineProcess.killed) {
    return engineProcess;
  }

  const pythonPath = options.pythonPath || 'python3';

  engineProcess = spawn(pythonPath, ['-u', '-c', BRIDGE_SCRIPT], {
    stdio: ['pipe', 'pipe', 'pipe'],
    env: {
      ...process.env,
      PYTHONPATH: LPTE_PYTHON_DIR,
    },
  });

  engineProcess.on('error', (err) => {
    console.error('LPTE engine error:', err.message);
    engineProcess = null;
  });

  engineProcess.on('exit', () => {
    engineProcess = null;
  });

  return engineProcess;
}

/**
 * Send a command to the Python engine and get the result.
 */
function sendCommand(command: string, args: Record<string, unknown>): Promise<LpteResult> {
  return new Promise((resolve, reject) => {
    const engine = getEngine();
    let responseData = '';

    const onData = (chunk: Buffer) => {
      responseData += chunk.toString();
      try {
        const response = JSON.parse(responseData);
        engine.stdout?.off('data', onData);
        resolve(response);
      } catch {
        // Not complete JSON yet, keep buffering
      }
    };

    engine.stdout?.on('data', onData);

    engine.stderr?.on('data', (chunk: Buffer) => {
      // Log stderr but don't reject (Python prints warnings to stderr)
    });

    const payload = JSON.stringify({ command, ...args }) + '\n';
    engine.stdin?.write(payload);

    // Timeout after 5 seconds
    setTimeout(() => {
      engine.stdout?.off('data', onData);
      reject(new Error('LPTE engine timeout'));
    }, 5000);
  });
}

/**
 * Analyze text for toxic content.
 */
export async function analyze(
  text: string,
  options: LpteOptions = {}
): Promise<LpteResult> {
  const { languageCode = 'en', threshold = 0.6 } = options;
  return sendCommand('analyze', { text, languageCode, threshold });
}

/**
 * Quick toxicity check.
 */
export async function isToxic(
  text: string,
  options: LpteOptions = {}
): Promise<boolean> {
  const result = await analyze(text, options);
  return result.isToxic;
}

/**
 * Sanitize text by masking toxic segments.
 */
export async function sanitize(
  text: string,
  languageCode: string = 'en',
  mask: string = '*'
): Promise<string> {
  const result = await sendCommand('sanitize', { text, languageCode, mask });
  return (result as unknown as { sanitized: string }).sanitized || text;
}

/**
 * Clean up the engine subprocess.
 */
export function destroy(): void {
  if (engineProcess) {
    engineProcess.kill();
    engineProcess = null;
  }
}

export default { analyze, isToxic, sanitize, destroy };
