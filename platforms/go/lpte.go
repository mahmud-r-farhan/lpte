// Package lpte provides Go bindings for the LPTE toxicity engine.
//
// The Go wrapper communicates with the Python LPTE engine via:
// 1. Embedded Python (cgo + Python C API) — production
// 2. Subprocess IPC — development/testing
//
// Usage:
//
//	engine, err := lpte.NewEngine("en")
//	if err != nil {
//	    log.Fatal(err)
//	}
//	defer engine.Close()
//
//	result, err := engine.Analyze("some text", 0.6)
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	if result.IsToxic {
//	    fmt.Printf("Toxic: %s (%.2f)\n", result.Severity, result.Confidence)
//	}
package lpte

import (
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
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

	return &Engine{
		languageCode: cfg.LanguageCode,
		threshold:    cfg.Threshold,
		pythonPath:   cfg.PythonPath,
	}, nil
}

// Analyze analyzes text for toxic content.
func (e *Engine) Analyze(text string, threshold ...float64) (*Result, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	t := e.threshold
	if len(threshold) > 0 {
		t = threshold[0]
	}

	return e.callPython("analyze", map[string]interface{}{
		"text":          text,
		"language_code": e.languageCode,
		"threshold":     t,
	})
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
	e.mu.Lock()
	defer e.mu.Unlock()

	m := "*"
	if len(mask) > 0 {
		m = mask[0]
	}

	// Build Python inline script
	script := fmt.Sprintf(`
import sys
sys.path.insert(0, "%s")
from lpte import LpteEngine
from lpte.languages import EnglishProfile, BengaliProfile

profiles = {"en": EnglishProfile, "bn": BengaliProfile}
profile = profiles.get("%s", EnglishProfile)
engine = LpteEngine(profile)

import json
print(json.dumps({"result": engine.sanitize("%s", "%s")}))
`, e.getLptePath(), e.languageCode, strings.ReplaceAll(text, `"`, `\"`), m)

	cmd := exec.Command(e.pythonPath, "-c", script)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return text, fmt.Errorf("sanitize failed: %w\n%s", err, output)
	}

	var resp struct {
		Result string `json:"result"`
	}
	if err := json.Unmarshal(output, &resp); err != nil {
		return text, fmt.Errorf("parse failed: %w", err)
	}

	return resp.Result, nil
}

// Close cleans up resources.
func (e *Engine) Close() error {
	return nil
}

func (e *Engine) callPython(command string, args map[string]interface{}) (*Result, error) {
	// Build Python inline script
	text := args["text"].(string)
	threshold := args["threshold"].(float64)

	script := fmt.Sprintf(`
import sys, json
sys.path.insert(0, "%s")
from lpte import LpteEngine
from lpte.languages import EnglishProfile, BengaliProfile

profiles = {"en": EnglishProfile, "bn": BengaliProfile}
profile = profiles.get("%s", EnglishProfile)
engine = LpteEngine(profile)

result = engine.analyze("""%s""", %v)
print(json.dumps({
    "is_toxic": result.is_toxic,
    "severity": result.severity.value,
    "confidence": result.confidence,
    "matched_terms": result.matched_terms
}))
`, e.getLptePath(), e.languageCode, text, threshold)

	cmd := exec.Command(e.pythonPath, "-c", script)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("analyze failed: %w\n%s", err, output)
	}

	var raw struct {
		IsToxic      bool     `json:"is_toxic"`
		Severity     int      `json:"severity"`
		Confidence   float64  `json:"confidence"`
		MatchedTerms []string `json:"matched_terms"`
	}
	if err := json.Unmarshal(output, &raw); err != nil {
		return nil, fmt.Errorf("parse failed: %w", err)
	}

	return &Result{
		IsToxic:      raw.IsToxic,
		Severity:     Severity(raw.Severity),
		Confidence:   raw.Confidence,
		MatchedTerms: raw.MatchedTerms,
	}, nil
}

func (e *Engine) getLptePath() string {
	return "."
}
