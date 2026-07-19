using System;
using System.Diagnostics;
using System.Text.Json;
using System.Threading.Tasks;

namespace Lpte
{
    /// <summary>
    /// LPTE — Local Profanity & Toxicity Engine for .NET.
    /// Communicates with the Python LPTE engine via subprocess IPC.
    /// </summary>
    public class Engine : IDisposable
    {
        private readonly string _languageCode;
        private readonly double _threshold;
        private readonly string _pythonPath;
        private bool _disposed;

        public Engine(string languageCode = "en", double threshold = 0.6, string pythonPath = "python3")
        {
            _languageCode = languageCode;
            _threshold = threshold;
            _pythonPath = pythonPath;
        }

        /// <summary>
        /// Analyze text for toxic content.
        /// </summary>
        public async Task<ClassificationResult> AnalyzeAsync(string text, double? threshold = null)
        {
            var t = threshold ?? _threshold;
            var script = $@"
import sys, json
sys.path.insert(0, '.')
from lpte import LpteEngine
from lpte.languages import EnglishProfile, BengaliProfile

profiles = {{'en': EnglishProfile, 'bn': BengaliProfile}}
profile = profiles.get('{_languageCode}', EnglishProfile)
engine = LpteEngine(profile)

result = engine.analyze("""{text.Replace("\"", "\\\"")}""", {t})
print(json.dumps({{
    'is_toxic': result.is_toxic,
    'severity': result.severity.value,
    'confidence': result.confidence,
    'matched_terms': result.matched_terms
}}))";

            var output = await RunPython(script);
            var raw = JsonSerializer.Deserialize<RawResult>(output);

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

        private async Task<string> RunPython(string script)
        {
            var psi = new ProcessStartInfo
            {
                FileName = _pythonPath,
                Arguments = $"-c \"{script.Replace("\"", "\\\"")}\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(psi);
            var output = await process.StandardOutput.ReadToEndAsync();
            await process.WaitForExitAsync();

            if (process.ExitCode != 0)
            {
                var error = await process.StandardError.ReadToEndAsync();
                throw new LpteException($"Python error: {error}");
            }

            return output;
        }

        public void Dispose()
        {
            if (!_disposed)
            {
                _disposed = true;
            }
        }
    }

    public enum Severity
    {
        None = 0,
        Low = 1,
        Medium = 2,
        High = 3,
        Critical = 4
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

    public class LpteException : Exception
    {
        public LpteException(string message) : base(message) { }
    }

    internal class RawResult
    {
        public bool IsToxic { get; set; }
        public int Severity { get; set; }
        public double Confidence { get; set; }
        public string[] MatchedTerms { get; set; } = Array.Empty<string>();
    }
}
