"""Seed QGIS3.ini (QSettings INI format) with the keys that load the qgis-mcp
plugin and auto-start its socket server.

usage: seed_ini.py <path-to-QGIS3.ini> <plugin-port>

QSettings string escaping is not configparser-compatible, so this makes
targeted line edits only and never rewrites lines it does not own.
"""

import sys

path = sys.argv[1]
port = sys.argv[2]

wanted = {
    "PythonPlugins": {"qgis_mcp_plugin": "true"},
    "qgis_mcp": {"autostart": "true", "port": port, "first_run": "false"},
}

with open(path, encoding="utf-8") as fh:
    lines = fh.read().splitlines()

out = []
pending = {}  # keys still to be written into the section being scanned


def flush_pending():
    for key, value in sorted(pending.items()):
        out.append(f"{key}={value}")
    pending.clear()


for line in lines:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        flush_pending()
        out.append(line)
        pending.update(wanted.pop(stripped[1:-1], {}))
        continue
    if pending and "=" in stripped:
        key = stripped.split("=", 1)[0]
        if key in pending:
            out.append(f"{key}={pending.pop(key)}")
            continue
    out.append(line)

flush_pending()

for section, keys in wanted.items():
    out.append("")
    out.append(f"[{section}]")
    for key, value in sorted(keys.items()):
        out.append(f"{key}={value}")

with open(path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
