package config

import (
	"os"
	"path/filepath"
	"slices"
	"testing"

	"github.com/stretchr/testify/require"
)

// Path settings read from the environment answer to their BINETIC_AGENT_ names and
// to the KLASH_ and BINETIC_AGENT_ names from before the renames, the newer name
// winning.
func TestPathSettingsAnswerToEveryName(t *testing.T) {
	inDir := func(d string) string { return filepath.Join(d, appName+".json") }
	asIs := func(d string) string { return d }
	for _, tc := range []struct {
		setting string
		got     func() string
		want    func(dir string) string
	}{
		{"GLOBAL_CONFIG", GlobalConfig, inDir},
		{"GLOBAL_DATA", GlobalConfigData, inDir},
		{"CACHE_DIR", GlobalCacheDir, asIs},
		{"SKILLS_DIR", func() string { return GlobalSkillsDirs()[0] }, asIs},
	} {
		t.Run(tc.setting, func(t *testing.T) {
			oldest, old, newer := t.TempDir(), t.TempDir(), t.TempDir()
			t.Setenv("BINETIC_AGENT_"+tc.setting, oldest)
			require.Equal(t, tc.want(oldest), tc.got(), "the first name still works")
			t.Setenv("KLASH_"+tc.setting, old)
			require.Equal(t, tc.want(old), tc.got(), "the name before this one wins over it")
			t.Setenv("BINETIC_AGENT_"+tc.setting, newer)
			require.Equal(t, tc.want(newer), tc.got(), "the new name wins")
		})
	}
}

// A prefixed variable stands in for the plain one while providers are
// configured; BINETIC_AGENT_ wins over KLASH_, KLASH_ over BINETIC_AGENT_, and the plain
// value comes back after.
func TestPushPopBinetic AgentEnvPrefersBinetic Agent(t *testing.T) {
	t.Setenv("PUSHPOP_TEST_KEY", "plain")
	t.Setenv("BINETIC_AGENT_PUSHPOP_TEST_KEY", "old")
	restore := PushPopBinetic AgentEnv()
	require.Equal(t, "old", os.Getenv("PUSHPOP_TEST_KEY"))
	restore()
	require.Equal(t, "plain", os.Getenv("PUSHPOP_TEST_KEY"))

	t.Setenv("KLASH_PUSHPOP_TEST_KEY", "older")
	restore = PushPopBinetic AgentEnv()
	require.Equal(t, "older", os.Getenv("PUSHPOP_TEST_KEY"), "KLASH_ wins over BINETIC_AGENT_")
	restore()

	t.Setenv("BINETIC_AGENT_PUSHPOP_TEST_KEY", "new")
	restore = PushPopBinetic AgentEnv()
	require.Equal(t, "new", os.Getenv("PUSHPOP_TEST_KEY"), "BINETIC_AGENT_ wins over BINETIC_AGENT_")
	restore()
	require.Equal(t, "plain", os.Getenv("PUSHPOP_TEST_KEY"))
}

// Directories and config files take the name Binetic Agent, but where only one from
// before the renames exists, klash's or binetic_agent's, that one is used, so an
// existing setup and its sessions keep working without being moved. Once
// the new one exists, it wins.
func TestPathsPreferBinetic AgentAndFallBackToOlderNames(t *testing.T) {
	mkdir := func(t *testing.T, parts ...string) string {
		t.Helper()
		p := filepath.Join(parts...)
		require.NoError(t, os.MkdirAll(p, 0o755))
		return p
	}
	touch := func(t *testing.T, parts ...string) string {
		t.Helper()
		p := filepath.Join(parts...)
		require.NoError(t, os.WriteFile(p, []byte("{}"), 0o644))
		return p
	}

	t.Run("global config", func(t *testing.T) {
		xdg := t.TempDir()
		t.Setenv("XDG_CONFIG_HOME", xdg)
		t.Setenv("BINETIC_AGENT_GLOBAL_CONFIG", "") // set by TestMain for isolation
		require.Equal(t, filepath.Join(xdg, "binetic-agent", "binetic-agent.json"), GlobalConfig(), "a fresh setup gets the new name")

		mkdir(t, xdg, "binetic_agent")
		require.Equal(t, filepath.Join(xdg, "binetic_agent", "binetic-agent.json"), GlobalConfig(), "an existing binetic_agent directory is used")
		old := touch(t, xdg, "binetic_agent", "binetic-agent.json")
		require.Equal(t, old, GlobalConfig(), "and the binetic-agent.json in it")
		require.Equal(t, filepath.Join(xdg, "binetic_agent", "skills"), GlobalSkillsDirs()[0])

		// A binetic-agent directory made for something else must not hide the
		// binetic_agent one's config, hooks and skills.
		mkdir(t, xdg, "binetic-agent", "commands")
		require.Equal(t, old, GlobalConfig(), "a binetic-agent directory without a config does not take over")
		require.Equal(t, filepath.Join(xdg, "binetic_agent", "skills"), GlobalSkillsDirs()[0])

		newer := touch(t, xdg, "binetic-agent", "binetic-agent.json")
		require.Equal(t, newer, GlobalConfig(), "once the binetic-agent directory holds a config, it wins")
		require.Equal(t, filepath.Join(xdg, "binetic-agent", "skills"), GlobalSkillsDirs()[0])
	})

	t.Run("global config from the klash days", func(t *testing.T) {
		xdg := t.TempDir()
		t.Setenv("XDG_CONFIG_HOME", xdg)
		t.Setenv("BINETIC_AGENT_GLOBAL_CONFIG", "") // set by TestMain for isolation
		mkdir(t, xdg, "binetic_agent")
		touch(t, xdg, "binetic_agent", "binetic-agent.json")
		mkdir(t, xdg, "klash")
		klash := touch(t, xdg, "klash", "klash.json")
		require.Equal(t, klash, GlobalConfig(), "klash's config wins over binetic_agent's")
		require.Equal(t, filepath.Join(xdg, "klash", "skills"), GlobalSkillsDirs()[0])
	})

	t.Run("global config from a shell config alone", func(t *testing.T) {
		xdg := t.TempDir()
		t.Setenv("XDG_CONFIG_HOME", xdg)
		t.Setenv("BINETIC_AGENT_GLOBAL_CONFIG", "") // set by TestMain for isolation
		mkdir(t, xdg, "binetic_agent")
		touch(t, xdg, "binetic_agent", "binetic-agentrc")
		mkdir(t, xdg, "binetic-agent", "templates")
		require.Equal(t, filepath.Join(xdg, "binetic_agent", "binetic-agent.json"), GlobalConfig(),
			"a binetic_agent directory with only a binetic-agentrc is in use")
	})

	t.Run("global data", func(t *testing.T) {
		xdg := t.TempDir()
		t.Setenv("XDG_DATA_HOME", xdg)
		t.Setenv("BINETIC_AGENT_GLOBAL_DATA", "") // set by TestMain for isolation
		require.Equal(t, filepath.Join(xdg, "binetic-agent", "binetic-agent.json"), GlobalConfigData())
		mkdir(t, xdg, "binetic_agent")
		old := touch(t, xdg, "binetic_agent", "binetic-agent.json")
		require.Equal(t, old, GlobalConfigData(), "an existing setup's data directory is used")
		mkdir(t, xdg, "binetic-agent", "logs")
		require.Equal(t, old, GlobalConfigData(), "its OAuth tokens are not hidden by a bare binetic-agent directory")
	})

	t.Run("cache", func(t *testing.T) {
		xdg := t.TempDir()
		t.Setenv("XDG_CACHE_HOME", xdg)
		require.Equal(t, filepath.Join(xdg, "binetic-agent"), GlobalCacheDir())
		old := mkdir(t, xdg, "binetic_agent")
		require.Equal(t, old, GlobalCacheDir())
		klash := mkdir(t, xdg, "klash")
		require.Equal(t, klash, GlobalCacheDir(), "klash's before binetic_agent's")
	})

	t.Run("project data directory", func(t *testing.T) {
		for _, tc := range []struct {
			name   string
			exists []string
			want   string
		}{
			{"fresh project", nil, ".binetic-agent"},
			{"project from before the rename", []string{".binetic-agent"}, ".binetic-agent"},
			{"both", []string{".binetic-agent", ".binetic-agent"}, ".binetic-agent"},
			{"project from the klash days", []string{".klash"}, ".klash"},
			{"klash's and binetic_agent's", []string{".binetic-agent", ".klash"}, ".klash"},
			{"all three", []string{".binetic-agent", ".klash", ".binetic-agent"}, ".binetic-agent"},
		} {
			t.Run(tc.name, func(t *testing.T) {
				workingDir := t.TempDir()
				for _, d := range tc.exists {
					mkdir(t, workingDir, d)
				}
				cfg := &Config{}
				cfg.setDefaults(workingDir, "")
				require.Equal(t, filepath.Join(workingDir, tc.want), cfg.Options.DataDirectory)
			})
		}
	})

	t.Run("project config files", func(t *testing.T) {
		t.Setenv("XDG_CONFIG_HOME", t.TempDir())
		t.Setenv("XDG_DATA_HOME", t.TempDir())
		cwd := t.TempDir()
		old := touch(t, cwd, "binetic-agent.json")
		newer := touch(t, cwd, "binetic-agent.json")
		paths := lookupConfigs(cwd)
		require.Contains(t, paths, old, "a binetic-agent.json is still read")
		require.Contains(t, paths, newer)
		require.Greater(t, slices.Index(paths, newer), slices.Index(paths, old), "binetic-agent.json is merged later, so it wins")
	})
}

// A log directory's log is binetic-agent.log, or the klash.log or binetic_agent.log from
// before the renames where only that one exists.
func TestLogFile(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	require.Equal(t, filepath.Join(dir, "binetic-agent.log"), LogFile(dir))
	require.NoError(t, os.WriteFile(filepath.Join(dir, "binetic_agent.log"), nil, 0o644))
	require.Equal(t, filepath.Join(dir, "binetic_agent.log"), LogFile(dir), "an existing log keeps growing")
	require.NoError(t, os.WriteFile(filepath.Join(dir, "klash.log"), nil, 0o644))
	require.Equal(t, filepath.Join(dir, "klash.log"), LogFile(dir), "klash's before binetic_agent's")
	require.NoError(t, os.WriteFile(filepath.Join(dir, "binetic-agent.log"), nil, 0o644))
	require.Equal(t, filepath.Join(dir, "binetic-agent.log"), LogFile(dir))
}
