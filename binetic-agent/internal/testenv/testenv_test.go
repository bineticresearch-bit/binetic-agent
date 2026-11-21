package testenv

import (
	"os"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestClearConfigVars(t *testing.T) {
	t.Setenv("BINETIC_AGENT_DISABLE_DEFAULT_PROVIDERS", "1")
	t.Setenv("BINETIC_AGENT_SOMETHING", "1")
	t.Setenv("KLASH_DISABLE_METRICS", "1")
	t.Setenv("BINETIC_AGENTED_NOT_OURS", "keep")
	t.Setenv("BINETIC_AGENT", "1") // the bare marker is not a setting
	t.Setenv("PATH_FOR_TEST", "keep")

	ClearConfigVars()

	_, ok := os.LookupEnv("BINETIC_AGENT_DISABLE_DEFAULT_PROVIDERS")
	require.False(t, ok, "a BINETIC_AGENT_ setting must be cleared")
	_, ok = os.LookupEnv("BINETIC_AGENT_SOMETHING")
	require.False(t, ok, "a BINETIC_AGENT_ setting must be cleared")
	_, ok = os.LookupEnv("KLASH_DISABLE_METRICS")
	require.False(t, ok, "a KLASH_ setting must be cleared")
	require.Equal(t, "keep", os.Getenv("BINETIC_AGENTED_NOT_OURS"), "only the exact prefixes are ours")
	require.Equal(t, "1", os.Getenv("BINETIC_AGENT"), "the bare marker is left alone")
	require.Equal(t, "keep", os.Getenv("PATH_FOR_TEST"))
}
