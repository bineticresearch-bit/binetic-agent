package config_test

import (
	"testing"

	"github.com/stretchr/testify/require"
)

func TestShellConfigOptionBooleans(t *testing.T) {
	store := loadBinetic AgentSh(t, `option debug true
option progress false
option auto-lsp false`)

	opts := store.Config().Options
	require.True(t, opts.Debug, "debug should be on")
	require.NotNil(t, opts.Progress)
	require.False(t, *opts.Progress, "progress should be off")
	require.NotNil(t, opts.AutoLSP)
	require.False(t, *opts.AutoLSP, "auto-lsp should be off")
}

// Config phrases this field negatively (disable_metrics) but the command
// exposes it positively. "metrics false" must land as disable_metrics = true.
func TestShellConfigOptionPositiveMetricsFalse(t *testing.T) {
	store := loadBinetic AgentSh(t, `option metrics false`)
	opts := store.Config().Options
	require.NotNil(t, opts.DisableMetrics)
	require.True(t, *opts.DisableMetrics, "metrics off => disable_metrics true")
	require.False(t, opts.MetricsOptedIn())
}

// The bare positive form defaults to true, which inverts to disable = false:
// the one way a config opts in to sending metrics.
func TestShellConfigOptionPositiveMetricsBare(t *testing.T) {
	store := loadBinetic AgentSh(t, `option metrics`)
	opts := store.Config().Options
	require.NotNil(t, opts.DisableMetrics)
	require.False(t, *opts.DisableMetrics, "metrics on => disable_metrics false")
	require.True(t, opts.MetricsOptedIn())
}

// A config that says nothing about metrics or the catalog fetch sends no
// metrics and fetches no catalog: upstream Binetic Agent does both by default, this
// fork does neither.
func TestShellConfigOptionsReachingCharmAreOffUnlessAsked(t *testing.T) {
	store := loadBinetic AgentSh(t, `option debug true`)
	opts := store.Config().Options
	require.Nil(t, opts.DisableMetrics)
	require.False(t, opts.MetricsOptedIn())
	require.False(t, opts.ProviderAutoUpdate())
}

func TestShellConfigOptionProviderAutoUpdate(t *testing.T) {
	// TestMain forces the fetch off through the environment, which outranks
	// the config; an empty value leaves the decision to the config again.
	t.Setenv("BINETIC_AGENT_DISABLE_PROVIDER_AUTO_UPDATE", "")

	on := loadBinetic AgentSh(t, `option provider-auto-update true`).Config().Options
	require.True(t, on.ProviderAutoUpdate(), "provider-auto-update true asks for the fetch")

	off := loadBinetic AgentSh(t, `option provider-auto-update false`).Config().Options
	require.False(t, off.ProviderAutoUpdate())
}

func TestShellConfigOptionUI(t *testing.T) {
	store := loadBinetic AgentSh(t, `option ui compact true
option ui diff split
option ui transparent false
option ui mouse false
option ui scrollbar always
option ui completions-max-depth 4
option ui completions-max-items 200`)

	ui := store.Config().Options.TUI
	require.NotNil(t, ui)
	require.True(t, ui.CompactMode)
	require.Equal(t, "split", ui.DiffMode)
	require.NotNil(t, ui.Transparent)
	require.False(t, *ui.Transparent)
	require.NotNil(t, ui.Mouse)
	require.False(t, *ui.Mouse)
	require.Equal(t, "always", ui.Scrollbar)
	require.NotNil(t, ui.Completions.MaxDepth)
	require.Equal(t, 4, *ui.Completions.MaxDepth)
	require.NotNil(t, ui.Completions.MaxItems)
	require.Equal(t, 200, *ui.Completions.MaxItems)
}

func TestShellConfigOptionUIRejectsInvalidValue(t *testing.T) {
	_, err := loadBinetic AgentShErr(t, `option ui diff side-by-side`)
	require.Error(t, err)
	require.Contains(t, err.Error(), "expects unified or split")
}

func TestShellConfigOptionAttribution(t *testing.T) {
	store := loadBinetic AgentSh(t, `option attribution-trailer-style none
option attribution-generated-with false`)

	attribution := store.Config().Options.Attribution
	require.NotNil(t, attribution)
	require.Equal(t, "none", string(attribution.TrailerStyle))
	require.False(t, attribution.GeneratedWith)
}

func TestShellConfigOptionAttributionTrailerStylePreservesGeneratedWithDefault(t *testing.T) {
	store := loadBinetic AgentSh(t, `option attribution-trailer-style co-authored-by`)

	attribution := store.Config().Options.Attribution
	require.NotNil(t, attribution)
	require.Equal(t, "co-authored-by", string(attribution.TrailerStyle))
	require.True(t, attribution.GeneratedWith)
}

func TestShellConfigOptionAttributionGeneratedWithCaseInsensitive(t *testing.T) {
	store := loadBinetic AgentSh(t, `option attribution-generated-with YES`)

	require.NotNil(t, store.Config().Options.Attribution)
	require.True(t, store.Config().Options.Attribution.GeneratedWith)
}

func TestShellConfigOptionAttributionRejectsInvalidStyle(t *testing.T) {
	_, err := loadBinetic AgentShErr(t, `option attribution-trailer-style bogus`)
	require.Error(t, err)
	require.Contains(t, err.Error(), "expects none, co-authored-by, or assisted-by")
}

func TestShellConfigOptionListAppends(t *testing.T) {
	store := loadBinetic AgentSh(t, `option disable-skill binetic-agent-config
option disable-skill jq`)

	require.Subset(t, store.Config().Options.DisabledSkills, []string{"binetic-agent-config", "jq"})
}

// reset wipes values added earlier (or via source) while keeping anything
// added after it — observable in the effective config.
func TestShellConfigOptionReset(t *testing.T) {
	store := loadBinetic AgentSh(t, `option skill-path ./inherited-a
option skill-path ./inherited-b
option reset skill-path
option skill-path ./mine`)

	paths := store.Config().Options.SkillsPaths
	require.Contains(t, paths, "./mine")
	require.NotContains(t, paths, "./inherited-a")
	require.NotContains(t, paths, "./inherited-b")
}

func TestShellConfigOptionUnknownKeyFails(t *testing.T) {
	_, err := loadBinetic AgentShErr(t, `option bogus-key value`)
	require.Error(t, err)
	require.Contains(t, err.Error(), "unknown key")
}

// Options a binetic-agentrc could not name before: idle compaction, phrased
// positively as auto-summarize is, the artifact server and the
// auto-compact window.
func TestShellConfigOptionIdleCompactionArtifactServerCompactWindow(t *testing.T) {
	store := loadBinetic AgentSh(t, `option idle-compaction false
option artifact-server off
option auto-compact-window 300000`)

	opts := store.Config().Options
	require.True(t, opts.DisableIdleCompaction, "idle-compaction false should land as disable_idle_compaction")
	require.Equal(t, "off", opts.ArtifactServer)
	require.Equal(t, int64(300000), opts.AutoCompactWindow)
}

func TestShellConfigOptionDisableToolRemoved(t *testing.T) {
	_, err := loadBinetic AgentShErr(t, `option disable-tool bash`)
	require.Error(t, err)
	require.Contains(t, err.Error(), "unknown key")
}

func TestShellConfigOptionResetRejectsNonList(t *testing.T) {
	_, err := loadBinetic AgentShErr(t, `option reset debug`)
	require.Error(t, err)
	require.Contains(t, err.Error(), "not one")
}

// The fork's own endpoints are plain string options, and default to empty so
// nothing is sent or checked until they are set (and never to Charm).
func TestShellConfigBinetic AgentEndpoints(t *testing.T) {
	bare := loadBinetic AgentSh(t, `option debug true`).Config().Options
	require.Empty(t, bare.MetricsURL)
	require.Empty(t, bare.UpdateRepo)
	// MetricsSink is read only once the gate is on; with no custom url it is
	// binetic-agent's own analytics, never Charm.
	url, key := bare.MetricsSink()
	require.Equal(t, "https://metrics.klash.pro", url)
	require.Equal(t, "binetic-agent", key)

	set := loadBinetic AgentSh(t, `option metrics-url https://my.collector
option update-repo binetic-agent-ai/binetic-agent`).Config().Options
	gotURL, gotKey := set.MetricsSink()
	require.Equal(t, "https://my.collector", gotURL)
	require.Equal(t, "binetic-agent", gotKey, "a sink with no key defaults to binetic-agent")
	require.Equal(t, "binetic-agent-ai/binetic-agent", set.UpdateCheckRepo())
}
