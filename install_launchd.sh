#!/bin/bash
# Install or uninstall voice-input launchd agents (service + menu bar).
# Usage:
#   ./install_launchd.sh          → install & start both
#   ./install_launchd.sh stop     → unload both (stop for now)
#   ./install_launchd.sh uninstall → remove both permanently

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

PLIST_DST="$HOME/Library/LaunchAgents/com.user.voice-input.plist"
LABEL="com.user.voice-input"

MENU_PLIST_DST="$HOME/Library/LaunchAgents/com.user.voice-input-menu.plist"
MENU_LABEL="com.user.voice-input-menu"

DOMAIN="gui/$(id -u)"

# ── Plist generators ──────────────────────────────────────────────────────────

generate_plist() {
    mkdir -p "$HOME/Library/LaunchAgents"
    local api_key_entry=""
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        api_key_entry="        <key>ANTHROPIC_API_KEY</key>
        <string>$ANTHROPIC_API_KEY</string>"
    fi
    cat > "$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$DIR/run.sh</string>
    </array>

    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>$DIR/voice_input.log</string>
    <key>StandardErrorPath</key>
    <string>$DIR/voice_input.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
$api_key_entry
    </dict>
</dict>
</plist>
EOF
}

generate_menu_plist() {
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$MENU_PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$MENU_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$DIR/run_menu_bar.sh</string>
    </array>

    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>10</integer>

    <!-- Required: rumps uses AppKit and needs a GUI session connection -->
    <key>ProcessType</key>
    <string>Interactive</string>

    <key>StandardOutPath</key>
    <string>$DIR/menu_bar.log</string>
    <key>StandardErrorPath</key>
    <string>$DIR/menu_bar.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF
}

# ── Load/unload helpers ───────────────────────────────────────────────────────

load_agent() {
    launchctl bootstrap "$DOMAIN" "$PLIST_DST" 2>/dev/null || launchctl load -w "$PLIST_DST" 2>/dev/null || true
}

unload_agent() {
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || launchctl unload "$PLIST_DST" 2>/dev/null || true
}

load_menu_agent() {
    launchctl bootstrap "$DOMAIN" "$MENU_PLIST_DST" 2>/dev/null || launchctl load -w "$MENU_PLIST_DST" 2>/dev/null || true
}

unload_menu_agent() {
    launchctl bootout "$DOMAIN/$MENU_LABEL" 2>/dev/null || launchctl unload "$MENU_PLIST_DST" 2>/dev/null || true
}

# Wait up to 15s for a service to fully stop (disappear from launchctl list)
wait_until_stopped() {
    local label="$1"
    local i=0
    while [ $i -lt 15 ]; do
        launchctl list "$label" &>/dev/null || return 0
        sleep 1; i=$((i+1))
    done
}

# Wait up to 8s for a service to appear in launchctl list, retry bootstrap once if needed
wait_for_service() {
    local label="$1" plist="$2" name="$3"
    local i=0
    while [ $i -lt 8 ]; do
        launchctl list "$label" &>/dev/null && echo "✓ $name" && return 0
        sleep 1; i=$((i+1))
    done
    # Not running — try bootstrap one more time explicitly
    launchctl bootstrap "$DOMAIN" "$plist" 2>/dev/null || true
    sleep 3
    launchctl list "$label" &>/dev/null && echo "✓ $name" && return 0
    echo "⚠  $name did not start — run: ./install_launchd.sh install"
}

# ── Commands ──────────────────────────────────────────────────────────────────

case "${1:-install}" in
  install)
    generate_plist
    generate_menu_plist
    unload_agent;      wait_until_stopped "$LABEL";      load_agent
    unload_menu_agent; wait_until_stopped "$MENU_LABEL"; load_menu_agent
    wait_for_service "$LABEL"      "$PLIST_DST"      "Voice input started"
    wait_for_service "$MENU_LABEL" "$MENU_PLIST_DST" "Menu bar started"
    echo "  Logs: $DIR/voice_input.log | $DIR/menu_bar.log"
    ;;
  stop)
    unload_agent
    unload_menu_agent
    echo "✓ Stopped (restarts at next login)."
    ;;
  uninstall)
    unload_agent;      rm -f "$PLIST_DST"
    unload_menu_agent; rm -f "$MENU_PLIST_DST"
    echo "✓ Removed. Will no longer start at login."
    ;;
  *)
    echo "Usage: $0 [install|stop|uninstall]"
    exit 1
    ;;
esac
