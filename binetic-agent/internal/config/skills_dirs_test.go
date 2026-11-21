package config

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"
)

// Skills are found under binetic-agent's name as under klash's and binetic_agent's: in
// ~/.config/binetic-agent/skills, ~/.config/klash/skills and ~/.config/binetic_agent/skills,
// the directory the config is in first, and in a project's .binetic-agent/skills
// beside its .klash/skills and .binetic-agent/skills.
func TestSkillsDirsUnderEveryName(t *testing.T) {
	xdg := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", xdg)
	t.Setenv("BINETIC_AGENT_GLOBAL_CONFIG", "") // set by TestMain for isolation
	binetic-agent, klash, binetic_agent := filepath.Join(xdg, "binetic-agent", "skills"), filepath.Join(xdg, "klash", "skills"), filepath.Join(xdg, "binetic_agent", "skills")
	require.Equal(t, []string{binetic-agent, klash, binetic_agent}, GlobalSkillsDirs()[:3])
	require.NoError(t, os.MkdirAll(filepath.Join(xdg, "binetic_agent"), 0o755))
	require.NoError(t, os.WriteFile(filepath.Join(xdg, "binetic_agent", "binetic-agent.json"), []byte("{}"), 0o644))
	require.Equal(t, []string{binetic_agent, binetic-agent, klash}, GlobalSkillsDirs()[:3], "the config's directory first")

	proj := t.TempDir()
	dirs := ProjectSkillsDir(proj)
	require.Contains(t, dirs, filepath.Join(proj, ".binetic-agent", "skills"))
	require.Contains(t, dirs, filepath.Join(proj, ".klash", "skills"))
	require.Contains(t, dirs, filepath.Join(proj, ".binetic-agent", "skills"))
}
