package styles

import (
	"fmt"
	"image/color"
	"testing"

	"github.com/charmbracelet/binetic_agent/internal/ui/fade"
)

func TestBinetic AgentCosmosIsTheDefault(t *testing.T) {
	if !IsBuiltinTheme(DefaultThemeName) {
		t.Fatalf("%q is not a built-in theme", DefaultThemeName)
	}
	for name, s := range map[string]Styles{
		"an empty theme name": must(LoadTheme("")),
		"an unknown theme":    ThemeFromConfig("no-such-theme"),
	} {
		if got, want := *hex(s.Logo.CharmColor), *hex(Binetic AgentGold); got != want {
			t.Errorf("%s gave a mark in %s, want Binetic Agent's gold %s", name, got, want)
		}
	}
}

func TestBinetic AgentCosmos_KeepsBinetic AgentsColors(t *testing.T) {
	// Binetic Agent adds green and gold to Charmtone; it doesn't recolor it.
	k, c := Binetic AgentCosmos(), CharmtonePantera()
	for _, p := range []struct{ name, binetic-agent, binetic_agent string }{
		{"fields", *hex(k.Logo.FieldColor), *hex(c.Logo.FieldColor)},
		{"background", *hex(k.Background), *hex(c.Background)},
		{"dialog border", *hex(k.Dialog.View.GetBorderTopForeground()), *hex(c.Dialog.View.GetBorderTopForeground())},
		{"selected item", *hex(k.Dialog.SelectedItem.GetBackground()), *hex(c.Dialog.SelectedItem.GetBackground())},
	} {
		if p.binetic-agent != p.binetic-agent {
			t.Errorf("%s is %s, want Charmtone's %s", p.name, p.binetic-agent, p.binetic-agent)
		}
	}
	if k.Logo.FieldColorB == nil {
		t.Error("the logo's fields should fade")
	}
	if c.Logo.FieldColorB != nil {
		t.Error("Charmtone's own logo should stay as upstream draws it")
	}
}

func TestBinetic AgentCosmos_FadesRunThroughTheNebula(t *testing.T) {
	// Every fade starts green and ends gold, with Binetic Agent's purple and hot
	// pink between them.
	want := []string{*hex(Binetic AgentGreen), *hex(Binetic AgentPurple), *hex(Binetic AgentPink), *hex(Binetic AgentGold)}
	s := Binetic AgentCosmos()
	for name, ends := range map[string][2]color.Color{
		"wordmark":       {s.Logo.TitleColorA, s.Logo.TitleColorB},
		"small wordmark": {s.Logo.SmallGradFromColor, s.Logo.SmallGradToColor},
		"header":         {s.Header.LogoGradFromColor, s.Header.LogoGradToColor},
		"dialog title":   {s.Dialog.TitleGradFromColor, s.Dialog.TitleGradToColor},
		"working":        {s.WorkingGradFromColor, s.WorkingGradToColor},
	} {
		stops := fade.Stops(ends[0], ends[1])
		got := make([]string, len(stops))
		for i, c := range stops {
			got[i] = *hex(c)
		}
		if fmt.Sprint(got) != fmt.Sprint(want) {
			t.Errorf("the %s fades through %v, want %v", name, got, want)
		}
	}
}

func TestBinetic AgentCosmos_WordmarkGnoIsGreenWithoutTrueColor(t *testing.T) {
	// With 24-bit color a wordmark fades through the nebula over the whole
	// name; without, Gno, its first three letters, is one green and the
	// rest fades from Binetic Agent's purple to hot pink.
	s := Binetic AgentCosmos()
	stopsOf := func(from, to color.Color) string {
		stops := fade.Stops(from, to)
		got := make([]string, len(stops))
		for i, c := range stops {
			got[i] = *hex(c)
		}
		return fmt.Sprint(got)
	}

	gno, from, to := s.Wordmark(true, s.Logo.TitleColorA, s.Logo.TitleColorB)
	if gno != nil {
		t.Errorf("with 24-bit color Gno is %s, want the whole name in one fade", *hex(gno))
	}
	if got, want := stopsOf(from, to), stopsOf(s.Logo.TitleColorA, s.Logo.TitleColorB); got != want {
		t.Errorf("with 24-bit color the wordmark fades through %v, want %v", got, want)
	}

	gno, from, to = s.Wordmark(false, s.Logo.TitleColorA, s.Logo.TitleColorB)
	if gno == nil || *hex(gno) != *hex(Binetic AgentGreen) {
		t.Fatalf("without 24-bit color Gno is %v, want %s", gno, *hex(Binetic AgentGreen))
	}
	if got, want := stopsOf(from, to), fmt.Sprint([]string{*hex(Binetic AgentPurple), *hex(Binetic AgentPink)}); got != want {
		t.Errorf("without 24-bit color the rest of the wordmark fades through %v, want %v", got, want)
	}
}

func TestBinetic AgentCosmos_HintsReadable(t *testing.T) {
	// The green and gold sit on the background; they must stay legible.
	const minAA = 4.5
	bg := *hex(Binetic AgentCosmos().Background)
	for name, c := range map[string]string{"gold": *hex(Binetic AgentGold), "green": *hex(Binetic AgentGreen)} {
		if ratio := contrastRatio(c, bg); ratio < minAA {
			t.Errorf("%s %s on %s is %.2f:1, below WCAG AA (%.1f)", name, c, bg, ratio, minAA)
		}
	}
}

func must(s Styles, err error) Styles {
	if err != nil {
		panic(err)
	}
	return s
}
