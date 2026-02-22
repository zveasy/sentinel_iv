#!/bin/sh
# Install Harmony Bridge for production: create hb user, install to /opt/hb, set permissions.
# Run with sudo. Prefix is configurable via PREFIX (default /opt/hb).

set -e
PREFIX="${PREFIX:-/opt/hb}"
HB_USER="${HB_USER:-hb}"

echo "Installing to $PREFIX as user $HB_USER"

# Create user if missing (Linux)
if command -v useradd >/dev/null 2>&1; then
  if ! id "$HB_USER" >/dev/null 2>&1; then
    useradd -r -s /bin/false -d "$PREFIX" "$HB_USER" || true
  fi
fi

mkdir -p "$PREFIX"/{bin,config,daemon_output}
# Copy or link your kit here; this script assumes files are already in PREFIX or you copy them
# cp -r hb hb_core app schemas config/*.yaml "$PREFIX/"
# cp bin/hb "$PREFIX/bin/"

chown -R "$HB_USER:$HB_USER" "$PREFIX"
chmod 750 "$PREFIX/daemon_output"
chmod 750 "$PREFIX"

# systemd
if [ -d /etc/systemd/system ] && [ -f deploy/hb-daemon.service ]; then
  sed "s|/opt/hb|$PREFIX|g" deploy/hb-daemon.service > /etc/systemd/system/hb-daemon.service
  systemctl daemon-reload
  echo "Installed systemd unit: hb-daemon.service. Enable with: systemctl enable --now hb-daemon"
fi

echo "Install complete. Reports and DB: $PREFIX/daemon_output and $PREFIX/runs.db (chmod 750, owner $HB_USER)."
