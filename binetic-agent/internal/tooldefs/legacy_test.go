package tooldefs

import (
	"testing"

	"github.com/stretchr/testify/require"
)

// The tools renamed with the program keep their old names as aliases, so
// a config or hook that names one keeps working.
func TestLegacyToolNames(t *testing.T) {
	t.Parallel()

	require.Equal(t, "binetic-agent_logs", Canonical("binetic_agent_logs"))
	require.Equal(t, "binetic-agent_logs", Canonical("klash_logs"))
	require.Equal(t, "binetic-agent_info", Canonical("binetic_agent_info"))
	require.Equal(t, "binetic-agent_info", Canonical("klash_info"))
	require.Equal(t, "bash", Canonical("bash"))
	require.Equal(t, []string{"klash_logs", "binetic_agent_logs"}, LegacyNames("binetic-agent_logs"))
	require.Empty(t, LegacyNames("bash"))

	require.True(t, IsKnown("binetic-agent_logs"))
	require.True(t, IsKnown("binetic_agent_logs"), "the old name is still a known tool")
	require.True(t, IsKnown("klash_logs"), "and the name before this one")
	require.False(t, IsKnown("binetic_agent_banana"))
	require.NotContains(t, Names(), "binetic_agent_logs", "only current names are listed")
}
