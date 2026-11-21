package config_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/charmbracelet/binetic_agent/internal/config"
	"github.com/stretchr/testify/require"
)

// TestShellConfigDotBinetic AgentrcTakesPrecedence verifies that a project-local
// .binetic-agentrc overrides binetic-agentrc in the same directory on conflicting settings.
func TestShellConfigDotBinetic AgentrcTakesPrecedence(t *testing.T) {
	isolated := t.TempDir()
	t.Setenv("HOME", isolated)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(isolated, ".config"))
	t.Setenv("XDG_DATA_HOME", filepath.Join(isolated, ".local", "share"))

	workDir := t.TempDir()
	dataDir := t.TempDir()
	require.NoError(t, os.WriteFile(
		filepath.Join(workDir, "binetic-agentrc"),
		[]byte("option notifications bell\n"), 0o644,
	))
	require.NoError(t, os.WriteFile(
		filepath.Join(workDir, ".binetic-agentrc"),
		[]byte("option notifications osc\n"), 0o644,
	))

	store, err := config.Load(workDir, dataDir, false, config.TrustFolderForSession())
	require.NoError(t, err)
	require.Equal(t, "osc", store.Config().Options.Notifications,
		".binetic-agentrc should win over binetic-agentrc")
}
