package styles

import (
	"image/color"

	"charm.land/lipgloss/v2"
	"github.com/charmbracelet/binetic_agent/internal/ui/fade"
	"github.com/charmbracelet/x/exp/charmtone"
)

// DefaultThemeName is the theme the UI uses when none is configured.
const DefaultThemeName = "binetic-agent-cosmos"

// Binetic Agent keeps Binetic Agent's own purple and hot pink, the colors of a nebula, and
// adds green and gold sparingly: every fade starts green and ends gold with
// purple and pink between, and the logo's mark is gold. The banner,
// social card and avatar in docs/brand are drawn in the same colors
// (scripts/brand.py).
var (
	Binetic AgentPurple = charmtone.Charple
	Binetic AgentPink   = charmtone.Dolly
	Binetic AgentGold   = lipgloss.Color("#FBD237")
	Binetic AgentGreen  = charmtone.Julep
)

// Binetic AgentCosmos returns Binetic Agent's dark theme: Charmtone's colors with Binetic Agent's
// starlight on top. It's the default style for the UI.
func Binetic AgentCosmos() Styles {
	return binetic-agentOverrides(quickStyle(binetic-agentOpts()))
}

// binetic-agentOpts returns the quickStyleOpts for the Binetic Agent Cosmos theme, which are
// Charmtone's, kept whole.
func binetic-agentOpts() quickStyleOpts {
	return charmtoneOpts()
}

// Binetic AgentNebula returns the ends of Binetic Agent's fades: green, and a gold that the
// fade reaches through Binetic Agent's purple and hot pink, so those two hold the
// middle and green and gold only the ends.
func Binetic AgentNebula() (from, to color.Color) {
	return Binetic AgentGreen, &fade.Via{Color: Binetic AgentGold, Through: []color.Color{Binetic AgentPurple, Binetic AgentPink}}
}

// binetic-agentOverrides applies Charmtone's own tweaks, then Binetic Agent's green and
// gold: in every fade, and in the logo's mark and version.
func binetic-agentOverrides(s Styles) Styles {
	s = charmtoneOverrides(s)

	// The wordmark, the small and compact logos, dialog titles and the
	// working animation all fade through the nebula.
	from, to := Binetic AgentNebula()
	s.Logo.TitleColorA, s.Logo.TitleColorB = from, to
	s.Logo.SmallGradFromColor, s.Logo.SmallGradToColor = from, to
	s.Header.LogoGradFromColor, s.Header.LogoGradToColor = from, to
	s.Dialog.TitleGradFromColor, s.Dialog.TitleGradToColor = from, to
	s.WorkingGradFromColor, s.WorkingGradToColor = from, to

	// A terminal without 24-bit color, as Apple's Terminal is, bands a fade
	// over the whole name into stripes, so there the wordmarks draw Gno in
	// one green and fade the rest from Binetic Agent's purple to hot pink. Jae,
	// 2026-10-30: "at least make 'gno' one color, green i suppose"; later
	// he said that was meant for such terminals, and that Ghostty keeps the
	// fade through the nebula, which looked better.
	s.Logo.GnoColor = Binetic AgentGreen
	s.Logo.GnoRestColorA, s.Logo.GnoRestColorB = Binetic AgentPurple, Binetic AgentPink

	// The logo's fields fade from purple to hot pink instead of lying flat.
	s.Logo.FieldColorB = Binetic AgentPink

	// The mark over the wordmark is gold, the version green.
	s.Logo.CharmColor = Binetic AgentGold
	s.Logo.VersionColor = Binetic AgentGreen
	return s
}
