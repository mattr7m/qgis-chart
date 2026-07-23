#!/bin/sh
# Install the qgis-mcp plugin into the QGIS profile (on the home PVC) and seed
# the settings that bring its socket server up with QGIS. Runs in the main
# QGIS image (has git + python3). Idempotent: re-runs on every pod start and
# refreshes the plugin to ${PLUGIN_REF}.
set -eu

: "${NB_USER:?}" "${NB_UID:?}" "${NB_GID:?}"
: "${PLUGIN_REPO:?}" "${PLUGIN_REF:?}" "${PLUGIN_PORT:?}"

HOME_DIR="/home/${NB_USER}"
PROFILE_DIR="${HOME_DIR}/.local/share/QGIS/QGIS3/profiles/default"
PLUGINS_DIR="${PROFILE_DIR}/python/plugins"
INI_FILE="${PROFILE_DIR}/QGIS/QGIS3.ini"

# Populate the home from the image skeleton before writing anything: the
# image's own populate hook (start-notebook.d/10-populate.sh) only copies
# top-level entries missing from the home, so if this script created .config/
# .local first, the skel's Xfce defaults would be skipped forever. No-clobber
# merge keeps existing user files authoritative.
if [ -d /var/backups/skel ] && [ ! -f "${HOME_DIR}/.populated" ]; then
  cp -an /var/backups/skel/. "${HOME_DIR}/"
  date -uIseconds > "${HOME_DIR}/.populated"
  echo "home populated from image skel"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
git clone --quiet --depth 1 --branch "${PLUGIN_REF}" "${PLUGIN_REPO}" "${tmp}/qgis-mcp"

mkdir -p "${PLUGINS_DIR}"
rm -rf "${PLUGINS_DIR}/qgis_mcp_plugin"
cp -r "${tmp}/qgis-mcp/qgis_mcp_plugin" "${PLUGINS_DIR}/qgis_mcp_plugin"

# Enable the plugin + socket-server autostart in the profile's QGIS3.ini
mkdir -p "$(dirname "${INI_FILE}")"
touch "${INI_FILE}"
python3 /scripts/seed_ini.py "${INI_FILE}" "${PLUGIN_PORT}"

# PyQGIS fallback that starts the plugin's server if the settings route fails
cp /scripts/qgis_startup.py "${PROFILE_DIR}/python/startup.py"

# Run QGIS under a supervisor so a crash relaunches it within the live Xfce
# session (the plugin's autostart re-fires each launch, so the qgis-mcp socket
# self-heals in seconds). The desktop-kicker only brings up / respawns the whole
# session; an in-process QGIS crash is this supervisor's job. The Xfce autostart
# launches the supervisor at session start.
mkdir -p "${HOME_DIR}/.local/bin" "${HOME_DIR}/.config/autostart"
cp /scripts/qgis-supervise.sh "${HOME_DIR}/.local/bin/qgis-mcp-supervise.sh"
chmod 0755 "${HOME_DIR}/.local/bin/qgis-mcp-supervise.sh"
cat > "${HOME_DIR}/.config/autostart/qgis-mcp.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=QGIS (qgis-mcp autostart + crash supervisor)
Comment=Installed by qgis-chart; runs QGIS under a restart loop so the qgis-mcp socket self-heals on crash
Exec=${HOME_DIR}/.local/bin/qgis-mcp-supervise.sh
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP

# Render output dir for the 3D gallery: create it user-owned before any
# subPath mount would materialize it root-owned on a fresh PVC
mkdir -p "${HOME_DIR}/qgis3d"

chown -R "${NB_UID}:${NB_GID}" "${HOME_DIR}/.local/share/QGIS" \
  "${HOME_DIR}/.local/bin" "${HOME_DIR}/.config/autostart" \
  "${HOME_DIR}/qgis3d" 2>/dev/null || true
echo "qgis-mcp plugin (${PLUGIN_REF}) installed; autostart seeded, socket port ${PLUGIN_PORT}"
