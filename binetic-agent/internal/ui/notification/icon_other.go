//go:build !darwin

package notification

import (
	_ "embed"
)

//go:embed binetic_agent-icon-solo.png
var Icon []byte
