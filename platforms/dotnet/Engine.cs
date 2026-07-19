using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;

namespace Lpte
{
    /// <summary>
    /// LPTE — Local Profanity & Toxicity Engine for .NET.
    /// Communicates with the Python engine via JSON IPC over stdin/stdout.
    /// User input is NEVER interpolated into Python code.
    /// </summary>
    public class Engine : IDisposable
    {
        private readonly string _languageCode;
        private readonly double _threshold;
        private readonly string _pythonPath;
        private Process _process;
        private StreamWriter _stdin;
        private bool _disposed;

        public Engine(string languageCode = "en", double threshold = 0.6, string pythonPath = "python3")
        {
            _languageCode = languageCode;
            _threshold = threshold;
            _pythonPath = pythonPath;
            StartProcess();
        }

        private void StartProcess()
        {
            var bridgeScript = GetBridgeScript();

            _process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = _pythonPath,
                    Arguments = $"-u -c \"{bridgeScript}\"",
                    RedirectStandardInput = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                }
            };

            _process.Start();
            _stdin = _process.StandardInput;
        }

        /// <summary>
        /// Analyze text for toxic content.
        /// </summary>
        public async Task<ClassificationResult> AnalyzeAsync(string text, double? threshold = null)
        {
            var t = threshold ?? _threshold;
            var request = JsonSerializer.Serialize(new
            {
                command = "analyze",
                text,
                language_code = _languageCode,
                threshold = t
            });

            await _stdin.WriteLineAsync(request);
            await _stdin.FlushAsync();

            var responseLine = await _process.StandardOutput.ReadLineAsync();
            var raw = JsonSerializer.Deserialize<RawResult>(responseLine);

            return new ClassificationResult
            {
                IsToxic = raw.IsToxic,
                Severity = (Severity)raw.Severity,
                Confidence = raw.Confidence,
                MatchedTerms = raw.MatchedTerms
            };
        }

        /// <summary>
        /// Quick toxicity check.
        /// </summary>
        public async Task<bool> IsToxicAsync(string text, double? threshold = null)
        {
            var result = await AnalyzeAsync(text, threshold);
            return result.IsToxic;
        }

        /// <summary>
        /// Synchronous analyze (blocks until complete).
        /// </summary>
        public ClassificationResult Analyze(string text, double? threshold = null)
        {
            return AnalyzeAsync(text, threshold).GetAwaiter().GetResult();
        }

        /// <summary>
        /// Synchronous toxicity check.
        /// </summary>
        public bool IsToxic(string text, double? threshold = null)
        {
            return IsToxicAsync(text, threshold).GetAwaiter().GetResult();
        }

        public void Dispose()
        {
            if (!_disposed)
            {
                _stdin?.Close();
                if (!_process.HasExited)
                {
                    _process.Kill();
                }
                _process?.Dispose();
                _disposed = true;
            }
        }

        private static string GetBridgeScript()
        {
            return @"import sys, json
from lpte.core.engine import LpteEngine
engines = {}
def get_engine(lang):
    if lang not in engines:
        if lang == 'bn':
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
        engine = get_engine(req.get('language_code', 'en'))
        cmd = req.get('command', 'analyze')
        if cmd == 'analyze':
            r = engine.analyze(req['text'], req.get('threshold', 0.6))
            print(json.dumps({'is_toxic': r.is_toxic, 'severity': r.severity.value, 'confidence': r.confidence, 'matched_terms': r.matched_terms}))
        else:
            print(json.dumps({'error': 'unknown command'}))
    except Exception as e:
        print(json.dumps({'error': str(e)}))";
        }
    }

    public enum Severity
    {
        None = 0, Low = 1, Medium = 2, High = 3, Critical = 4
    }

    public class ClassificationResult
    {
        public bool IsToxic { get; set; }
        public Severity Severity { get; set; }
        public double Confidence { get; set; }
        public string[] MatchedTerms { get; set; } = Array.Empty<string>();

        public override string ToString() =>
            $"Toxic={IsToxic}, Severity={Severity}, Confidence={Confidence:F2}";
    }

    internal class RawResult
    {
        public bool IsToxic { get; set; }
        public int Severity { get; set; }
        public double Confidence { get; set; }
        public string[] MatchedTerms { get; set; } = Array.Empty<string>();
    }
}
