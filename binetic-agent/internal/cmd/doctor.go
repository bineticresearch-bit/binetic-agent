package cmd

import (
	"errors"
	"fmt"
	"os/exec"
	"strings"

	"github.com/charmbracelet/binetic_agent/internal/config"
	"github.com/charmbracelet/binetic_agent/internal/doctor"
	"github.com/spf13/cobra"
)

var doctorCmd = &cobra.Command{
	Use:   "doctor",
	Short: "Check that Binetic Agent can run here: config, providers, models, hooks and tools",
	Long: `Check the setup Binetic Agent runs with in this directory, as Claude Code's
doctor does: the config files it loads, the providers it can use and why it
cannot use the others, the models it picks, the hooks it runs, and whether
the programs it calls are installed. It exits non-zero when Binetic Agent could not
run a turn here.`,
	Example: `
# Check the setup for the current directory
binetic-agent doctor
  `,
	RunE: func(cmd *cobra.Command, args []string) error {
		cwd, err := ResolveCwd(cmd)
		if err != nil {
			return err
		}
		dataDir, _ := cmd.Flags().GetString("data-dir")
		store, err := config.Init(cwd, dataDir, false)
		if err != nil {
			fmt.Fprintf(cmd.OutOrStdout(), "✗ config: %v\n", err)
			return errors.New("the config does not load; see above")
		}
		lines, ok := doctor.Report(store, exec.LookPath)
		fmt.Fprintln(cmd.OutOrStdout(), strings.Join(lines, "\n"))
		if !ok {
			return errors.New("binetic-agent could not run a turn here; see above")
		}
		return nil
	},
}
