#!/bin/bash
# Install or uninstall the voice-input launchd agent.
# Usage:
#   ./install_launchd.sh          → install & start
#   ./install_launchd.sh stop     → unload (stop for now)
#   ./install_launchd.sh uninstall → remove permanently

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_DST="$HOME/Library/LaunchAgents/com.user.voice-input.plist"
LABEL="com.user.voice-input"

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

DOMAIN="gui/$(id -u)"

load_agent() {
    launchctl bootstrap "$DOMAIN" "$PLIST_DST" 2>/dev/null || launchctl load -w "$PLIST_DST" 2>/dev/null || true
}

unload_agent() {
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || launchctl unload "$PLIST_DST" 2>/dev/null || true
}

case "${1:-install}" in
  install)
    generate_plist
    unload_agent
    load_agent
    echo "✓ Installed and started. Logs: $DIR/voice_input.log"
    ;;
  stop)
    unload_agent && echo "✓ Stopped (restarts at next login)."
    ;;
  uninstall)
    unload_agent
    rm -f "$PLIST_DST"
    echo "✓ Removed. Will no longer start at login."
    ;;
  *)
    echo "Usage: $0 [install|stop|uninstall]"
    exit 1
    ;;
esac
