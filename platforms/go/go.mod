// LPTE — Go bindings for the Local Profanity & Toxicity Engine.
//
// Provides on-device text toxicity analysis via Python subprocess IPC.
//
// Quick start:
//
//	engine, _ := lpte.NewEngine("en")
//	defer engine.Close()
//
//	result, _ := engine.Analyze("some text")
//	if result.IsToxic {
//	    fmt.Println("Blocked!")
//	}
module github.com/lpte/lpte

go 1.21
