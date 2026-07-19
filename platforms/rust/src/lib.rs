//! LPTE — Rust bindings for the Local Profanity & Toxicity Engine.
//!
//! Communicates with the Python engine via JSON IPC over stdin/stdout.
//! User input is NEVER interpolated into Python code.
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
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
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

#[derive(Serialize)]
struct IpcRequest {
    command: String,
    text: String,
    language_code: String,
    threshold: f64,
}

#[derive(Deserialize)]
struct IpcResponse {
    is_toxic: bool,
    severity: u8,
    confidence: f64,
    matched_terms: Vec<String>,
}

/// LPTE toxicity analysis engine.
pub struct Engine {
    language_code: String,
    threshold: f64,
    child: Mutex<Child>,
}

impl Engine {
    /// Create a new engine instance.
    pub fn new(language_code: &str, opts: Options) -> Result<Self, String> {
        let bridge_script = include_str!("bridge.py");

        let mut child = Command::new(&opts.python_path)
            .args(["-u", "-c", bridge_script])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start Python: {}", e))?;

        Ok(Engine {
            language_code: language_code.to_string(),
            threshold: opts.threshold,
            child: Mutex::new(child),
        })
    }

    fn send_request(&self, req: &IpcRequest) -> Result<IpcResponse, String> {
        let mut child = self.child.lock().map_err(|e| e.to_string())?;
        let stdin = child.stdin.as_mut().ok_or("No stdin")?;
        let stdout = child.stdout.as_mut().ok_or("No stdout")?;

        let mut request_json = serde_json::to_string(req).map_err(|e| e.to_string())?;
        request_json.push('\n');

        stdin
            .write_all(request_json.as_bytes())
            .map_err(|e| format!("Write failed: {}", e))?;
        stdin.flush().map_err(|e| format!("Flush failed: {}", e))?;

        let mut reader = BufReader::new(stdout);
        let mut line = String::new();
        reader
            .read_line(&mut line)
            .map_err(|e| format!("Read failed: {}", e))?;

        serde_json::from_str(&line).map_err(|e| format!("Parse failed: {}", e))
    }

    /// Analyze text for toxic content.
    pub fn analyze(&self, text: &str, threshold: Option<f64>) -> Result<Result, String> {
        let t = threshold.unwrap_or(self.threshold);

        let resp = self.send_request(&IpcRequest {
            command: "analyze".to_string(),
            text: text.to_string(),
            language_code: self.language_code.clone(),
            threshold: t,
        })?;

        Ok(Result {
            is_toxic: resp.is_toxic,
            severity: Severity::from_u8(resp.severity),
            confidence: resp.confidence,
            matched_terms: resp.matched_terms,
        })
    }

    /// Quick toxicity check.
    pub fn is_toxic(&self, text: &str, threshold: Option<f64>) -> Result<bool, String> {
        let result = self.analyze(text, threshold)?;
        Ok(result.is_toxic)
    }
}

impl Drop for Engine {
    fn drop(&mut self) {
        if let Ok(mut child) = self.child.lock() {
            let _ = child.kill();
        }
    }
}
