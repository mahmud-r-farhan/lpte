//! LPTE — Rust bindings for the Local Profanity & Toxicity Engine.
//!
//! Provides on-device text toxicity analysis. Communicates with the Python
//! LPTE engine via:
//! 1. PyO3 (embedded Python) — production
//! 2. Subprocess IPC — development/testing
//!
//! # Usage
//!
//! ```rust
//! use lpte::{Engine, Options};
//!
//! let engine = Engine::new("en", Options::default()).unwrap();
//! let result = engine.analyze("some text", None).unwrap();
//!
//! if result.is_toxic {
//!     println!("Toxic: {:?} ({:.2})", result.severity, result.confidence);
//! }
//! ```

use serde::{Deserialize, Serialize};
use std::process::Command;
use std::sync::Mutex;

/// Toxicity severity levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum Severity {
    None = 0,
    Low = 1,
    Medium = 2,
    High = 3,
    Critical = 4,
}

impl Severity {
    pub fn from_u8(v: u8) -> Self {
        match v {
            0 => Severity::None,
            1 => Severity::Low,
            2 => Severity::Medium,
            3 => Severity::High,
            _ => Severity::Critical,
        }
    }
}

/// Classification result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Result {
    pub is_toxic: bool,
    pub severity: Severity,
    pub confidence: f64,
    pub matched_terms: Vec<String>,
}

/// Engine configuration.
#[derive(Debug, Clone)]
pub struct Options {
    pub language_code: String,
    pub threshold: f64,
    pub python_path: String,
}

impl Default for Options {
    fn default() -> Self {
        Options {
            language_code: "en".to_string(),
            threshold: 0.6,
            python_path: "python3".to_string(),
        }
    }
}

/// LPTE toxicity analysis engine.
pub struct Engine {
    language_code: String,
    threshold: f64,
    python_path: String,
    _mutex: Mutex<()>,
}

impl Engine {
    /// Create a new engine instance.
    pub fn new(language_code: &str, opts: Options) -> Result<Self, String> {
        Ok(Engine {
            language_code: language_code.to_string(),
            threshold: opts.threshold,
            python_path: opts.python_path,
            _mutex: Mutex::new(()),
        })
    }

    /// Analyze text for toxic content.
    pub fn analyze(&self, text: &str, threshold: Option<f64>) -> Result<Result, String> {
        let t = threshold.unwrap_or(self.threshold);

        let script = format!(
            r#"
import sys, json
sys.path.insert(0, ".")
from lpte import LpteEngine
from lpte.languages import EnglishProfile, BengaliProfile

profiles = {{"en": EnglishProfile, "bn": BengaliProfile}}
profile = profiles.get("{lang}", EnglishProfile)
engine = LpteEngine(profile)

result = engine.analyze("""{text}""", {threshold})
print(json.dumps({{
    "is_toxic": result.is_toxic,
    "severity": result.severity.value,
    "confidence": result.confidence,
    "matched_terms": result.matched_terms
}}))
"#,
            lang = self.language_code,
            text = text.replace('"', "\\\""),
            threshold = t,
        );

        let output = Command::new(&self.python_path)
            .arg("-c")
            .arg(&script)
            .output()
            .map_err(|e| format!("Failed to run Python: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("Python error: {}", stderr));
        }

        let stdout = String::from_utf8_lossy(&output.stdout);
        let raw: RawResult =
            serde_json::from_str(&stdout).map_err(|e| format!("Parse error: {}", e))?;

        Ok(Result {
            is_toxic: raw.is_toxic,
            severity: Severity::from_u8(raw.severity),
            confidence: raw.confidence,
            matched_terms: raw.matched_terms,
        })
    }

    /// Quick toxicity check.
    pub fn is_toxic(&self, text: &str, threshold: Option<f64>) -> Result<bool, String> {
        let result = self.analyze(text, threshold)?;
        Ok(result.is_toxic)
    }
}

#[derive(Deserialize)]
struct RawResult {
    is_toxic: bool,
    severity: u8,
    confidence: f64,
    matched_terms: Vec<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_severity_from_u8() {
        assert_eq!(Severity::from_u8(0), Severity::None);
        assert_eq!(Severity::from_u8(1), Severity::Low);
        assert_eq!(Severity::from_u8(4), Severity::Critical);
    }
}
