#!/usr/bin/env bash
set -euo pipefail

# Restore Binetic system onto the Mac Studio from the staged migration bundle.
# Run this from macOS Terminal, not from the Linux VM.
BUNDLE="$(cd "$(dirname "$0")" && pwd)"
DEST_ROOT="${BINETIC_DEST_ROOT:-$HOME/binetic-runtime}"

echo "Binetic Mac Studio restore"
echo "bundle: $BUNDLE"
echo "dest:   $DEST_ROOT"

mkdir -p "$DEST_ROOT"

echo "[1/8] extracting Binetic superagent..."
tar -xzf "$BUNDLE/binetic-superagent.tar.gz" -C "$DEST_ROOT"

echo "[2/8] extracting Linux VM bin tools..."
tar -xzf "$BUNDLE/bin-tools.tar.gz" -C "$DEST_ROOT"

echo "[3/8] extracting my-agent / Convex source..."
tar -xzf "$BUNDLE/my-agent-no-live-db.tar.gz" -C "$DEST_ROOT"

echo "[4/8] restoring consistent Convex DB snapshot..."
mkdir -p "$DEST_ROOT/my-agent/.convex/local/default"
cp "$BUNDLE/convex_local_backend.sqlite3" \
   "$DEST_ROOT/my-agent/.convex/local/default/convex_local_backend.sqlite3"

echo "[5/8] copying models and llama.cpp..."
mkdir -p "$DEST_ROOT"
cp -a "$BUNDLE/models" "$DEST_ROOT/models"
cp -a "$BUNDLE/llama.cpp" "$DEST_ROOT/llama.cpp"

echo "[6/8] installing Mac model proxy on 8645 -> 127.0.0.1:8001..."
cp "$BUNDLE/model-proxy.mac.mjs" "$DEST_ROOT/model-proxy.mjs"

echo "[7/8] rewriting Linux paths..."
# Fix symlinks copied from the VM.
find "$DEST_ROOT/bin" -maxdepth 1 -type l -print0 2>/dev/null | while IFS= read -r -d '' link; do
  target="$(readlink "$link" || true)"
  new_target="${target//\/root\/agent-workspace\/binetic-superagent/$DEST_ROOT/binetic-superagent}"
  new_target="${new_target//\/root\/agent-workspace\/models/$DEST_ROOT/models}"
  new_target="${new_target//\/root\/agent-workspace\/llama.cpp/$DEST_ROOT/llama.cpp}"
  new_target="${new_target//\/root\/agent-workspace\/bin/$DEST_ROOT/bin}"
  new_target="${new_target//\/root\/agent-workspace/$DEST_ROOT}"
  new_target="${new_target//\/root\/my-agent/$DEST_ROOT/my-agent}"
  if [ "$new_target" != "$target" ]; then
    ln -sfn "$new_target" "$link"
  fi
done

# Patch text files that still contain VM-only paths.
grep -IrlZ --null \
  -e '/root/agent-workspace/binetic-superagent' \
  -e '/root/agent-workspace/models' \
  -e '/root/agent-workspace/llama.cpp' \
  -e '/root/agent-workspace/bin' \
  -e '/root/my-agent' \
  "$DEST_ROOT/binetic-superagent" "$DEST_ROOT/bin" "$DEST_ROOT/my-agent" 2>/dev/null \
| xargs -0 -r sed -i '' \
    -e "s#/root/agent-workspace/binetic-superagent#$DEST_ROOT/binetic-superagent#g" \
    -e "s#/root/agent-workspace/models#$DEST_ROOT/models#g" \
    -e "s#/root/agent-workspace/llama.cpp#$DEST_ROOT/llama.cpp#g" \
    -e "s#/root/agent-workspace/bin#$DEST_ROOT/bin#g" \
    -e "s#/root/my-agent#$DEST_ROOT/my-agent#g"

chmod +x "$DEST_ROOT/binetic-superagent"/*.py \
         "$DEST_ROOT/binetic-superagent"/*.sh \
         "$DEST_ROOT/binetic-superagent"/tests/*.py 2>/dev/null || true

echo "[8/8] creating macOS Binetic Agent launcher..."
cat >"$DEST_ROOT/bin/binetic-binetic-agent" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export PATH="$DEST_ROOT/bin:\$PATH"
export BINETIC_MAIN_INTERFACE="binetic-agent-tui"
python3 "$DEST_ROOT/binetic-superagent/binetic-cockpit.py" bootstrap >/tmp/binetic-bootstrap.json || true
BINETIC_AGENT_BIN="\$(/usr/bin/which -a binetic-agent 2>/dev/null | grep -v "$DEST_ROOT/bin/binetic-agent" | head -n 1 || true)"
if [ -z "\$BINETIC_AGENT_BIN" ]; then
  echo "native binetic-agent not found in PATH; install binetic-agent on macOS first" >&2
  exit 1
fi
exec "\$BINETIC_AGENT_BIN" \\
  --cwd "$DEST_ROOT/binetic-superagent" \\
  --append-system-prompt-file "$DEST_ROOT/binetic-superagent/BINETIC_SYSTEM_PROMPT.md" \\
  "\$@"
EOF
chmod +x "$DEST_ROOT/bin/binetic-binetic-agent"

cat <<EOF

Restore complete.

Start sequence on Mac Studio:

  1) Start Hermes/Kapitsa on 127.0.0.1:8001.
  2) Start the Binetic model proxy:
       node "$DEST_ROOT/model-proxy.mjs"
  3) Start Convex/Vite:
       cd "$DEST_ROOT/my-agent"
       npx convex dev --typecheck=disable --start 'npx vite --port 5273 --host'
  4) Open Binetic Agent:
       export PATH="$DEST_ROOT/bin:\$PATH"
       binetic-binetic-agent
  5) Start the live action terminal:
       "$DEST_ROOT/bin/binetic-live-terminal"

Binetic Agent route remains:
  127.0.0.1:8645/v1 -> 127.0.0.1:8001

Selected model remains:
  tencent/hy4-flash:free
EOF
