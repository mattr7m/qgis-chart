#!/bin/sh
# Keep QGIS running in the headless Xfce session. If QGIS exits (crash), relaunch
# it — the qgis-mcp plugin's autostart re-fires on each start, so the plugin
# socket (127.0.0.1:9876) returns within seconds with no external action. This
# covers the gap the desktop-kicker cannot: the kicker only brings up / respawns
# the whole session (via the /desktop proxy); an in-process QGIS crash inside a
# still-live session is invisible to it, and the Xfce autostart fires only at
# session login. This supervisor is that missing app-level restart.
#
# In-memory project state is lost on a crash; reload the .qgz from the PVC.
# Exponential backoff (capped) avoids a hot loop if QGIS dies immediately, e.g.
# on a GL/driver fault. Runs from the Xfce autostart, so DISPLAY is already set.
log="${HOME}/.qgis-mcp-supervise.log"
delay=3
max=120

while true; do
  echo "$(date -uIseconds) launching qgis" >> "$log"
  start=$(date +%s)
  qgis
  rc=$?
  ran=$(( $(date +%s) - start ))
  if [ "$ran" -lt 15 ]; then
    delay=$(( delay * 2 ))
    [ "$delay" -gt "$max" ] && delay="$max"
  else
    delay=3
  fi
  echo "$(date -uIseconds) qgis exited rc=${rc} after ${ran}s; restarting in ${delay}s" >> "$log"
  sleep "$delay"
done
