// Package lpte provides Go bindings for the LPTE toxicity engine.
//
// Communicates with the Python LPTE engine via JSON IPC over stdin/stdout.
// User input is NEVER interpolated into Python code — all data passes through JSON.
//
// Usage:
//
//	engine, err := lpte.NewEngine("en")
//	defer engine.Close()
//
//	result, err := engine.Analyze("some text")
//	if result.IsToxic {
//	    fmt.Printf("Toxic: %s (%.2f)\n", result.Severity, result.Confidence)
//	}
package lpte

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os/exec"
	"sync"
)

// Severity represents the toxicity severity level.
type Severity int

const (
	SeverityNone Severity = iota
	SeverityLow
	SeverityMedium
	SeverityHigh
	SeverityCritical
)

func (s Severity) String() string {
	return [...]string{"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"}[s]
}

// Result holds the classification output.
type Result struct {
	IsToxic      bool     `json:"is_toxic"`
	Severity     Severity `json:"severity"`
	Confidence   float64  `json:"confidence"`
	MatchedTerms []string `json:"matched_terms"`
}

// Options configures the engine.
type Options struct {
	LanguageCode string
	Threshold    float64
	PythonPath   string
}

// Engine wraps the Python LPTE engine.
type Engine struct {
	languageCode string
	threshold    float64
	pythonPath   string
	cmd          *exec.Cmd
	stdin        io.WriteCloser
	scanner      *bufio.Scanner
	mu           sync.Mutex
}

// NewEngine creates a new LPTE engine instance.
func NewEngine(languageCode string, opts ...Options) (*Engine, error) {
	cfg := Options{
		LanguageCode: languageCode,
		Threshold:    0.6,
		PythonPath:   "python3",
	}
	if len(opts) > 0 {
		cfg = opts[0]
	}

	// Start a persistent Python process for IPC
	cmd := exec.Command(cfg.PythonPath, "-u", "-c", bridgeScript)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to create stdin pipe: %w", err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to create stdout pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to start Python: %w", err)
	}

	return &Engine{
		languageCode: cfg.LanguageCode,
		threshold:    cfg.Threshold,
		pythonPath:   cfg.PythonPath,
		cmd:          cmd,
		stdin:        stdin,
		scanner:      bufio.NewScanner(stdout),
	}, nil
}

type ipcRequest struct {
	Command      string  `json:"command"`
	Text         string  `json:"text"`
	LanguageCode string  `json:"language_code"`
	Threshold    float64 `json:"threshold"`
	Mask         string  `json:"mask,omitempty"`
}

type ipcResponse struct {
	IsToxic      bool     `json:"is_toxic"`
	Severity     int      `json:"severity"`
	Confidence   float64  `json:"confidence"`
	MatchedTerms []string `json:"matched_terms"`
	Sanitized    string   `json:"sanitized,omitempty"`
}

func (e *Engine) sendRequest(req ipcRequest) (*ipcResponse, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	data, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}
	data = append(data, '\n')

	if _, err := e.stdin.Write(data); err != nil {
		return nil, fmt.Errorf("write to engine: %w", err)
	}

	if !e.scanner.Scan() {
		return nil, fmt.Errorf("engine closed: %w", e.scanner.Err())
	}

	var resp ipcResponse
	if err := json.Unmarshal(e.scanner.Bytes(), &resp); err != nil {
		return nil, fmt.Errorf("parse response: %w", err)
	}

	return &resp, nil
}

// Analyze analyzes text for toxic content.
func (e *Engine) Analyze(text string, threshold ...float64) (*Result, error) {
	t := e.threshold
	if len(threshold) > 0 {
		t = threshold[0]
	}

	resp, err := e.sendRequest(ipcRequest{
		Command:      "analyze",
		Text:         text,
		LanguageCode: e.languageCode,
		Threshold:    t,
	})
	if err != nil {
		return nil, err
	}

	return &Result{
		IsToxic:      resp.IsToxic,
		Severity:     Severity(resp.Severity),
		Confidence:   resp.Confidence,
		MatchedTerms: resp.MatchedTerms,
	}, nil
}

// IsToxic performs a quick toxicity check.
func (e *Engine) IsToxic(text string, threshold ...float64) (bool, error) {
	result, err := e.Analyze(text, threshold...)
	if err != nil {
		return false, err
	}
	return result.IsToxic, nil
}

// Sanitize masks toxic segments in text.
func (e *Engine) Sanitize(text string, mask ...string) (string, error) {
	m := "*"
	if len(mask) > 0 {
		m = mask[0]
	}

	resp, err := e.sendRequest(ipcRequest{
		Command:      "sanitize",
		Text:         text,
		LanguageCode: e.languageCode,
		Mask:         m,
	})
	if err != nil {
		return text, err
	}

	return resp.Sanitized, nil
}

// Close shuts down the Python engine process.
func (e *Engine) Close() error {
	e.stdin.Close()
	return e.cmd.Process.Kill()
}

// bridgeScript is the persistent Python IPC bridge.
// All user input arrives via JSON on stdin — NEVER interpolated into code.
const bridgeScript = `
import sys, json
from lpte.core.engine import LpteEngine
from lpte.core.loader import LanguagePackLoader

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
`
