package cmd

import (
	"os"
	"testing"

	"github.com/charmbracelet/binetic_agent/internal/testenv"
)

// TestMain clears inherited BINETIC_AGENT_* and BINETIC_AGENT_* settings, so these tests
// pass or fail on the code alone and not on the environment of whoever runs
// them; see testenv.ClearConfigVars.
func TestMain(m *testing.M) {
	os.Exit(testenv.Run(m))
}
