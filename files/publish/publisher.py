"""Debounced 2D publish watcher (qgis-agent tasks/qgis-publish-pipeline.md).

Copies the live project to the published project whenever the live file has
changed AND been idle for the debounce window — so the public map (served by
the OGC sidecar from the published copy) never shows a half-finished edit.
An operator can force an immediate publish by creating the trigger file
(e.g. via execute_code: open(TRIGGER,'w').close()); the watcher publishes and
removes it. This replaces the save-as publish ritual that silently repointed
the live QGIS session (qgis-agent#42).

Copy is atomic (temp file + os.replace in the destination directory) so the
OGC server can never read a torn .qgz. Mounts: the home tree read-only at
/src-home (source); only published/ read-write at /pub (dest + trigger).
Stdlib only.
"""

import os
import shutil
import time

SRC = os.environ["PUBLISH_SOURCE"]  # under the ro mount
DST = os.environ["PUBLISH_DEST"]  # under the rw mount
TRIGGER = os.environ.get("PUBLISH_TRIGGER", os.path.join(os.path.dirname(DST), ".publish-now"))
DEBOUNCE = int(os.environ.get("PUBLISH_DEBOUNCE_SECONDS", "60"))
POLL = int(os.environ.get("PUBLISH_POLL_SECONDS", "5"))


def src_mtime():
    try:
        return os.stat(SRC).st_mtime
    except OSError:
        return None


def publish(mtime, reason):
    tmp = DST + ".tmp"
    shutil.copyfile(SRC, tmp)
    os.replace(tmp, DST)
    print(f"published {SRC} -> {DST} ({reason}, src mtime {int(mtime)})", flush=True)
    return mtime


last_published = None
m = src_mtime()
if m is not None and os.path.exists(DST) and os.stat(DST).st_mtime >= m:
    last_published = m  # dest already current; don't republish on start

print(
    f"watching {SRC} (debounce {DEBOUNCE}s, poll {POLL}s); trigger: {TRIGGER}",
    flush=True,
)
while True:
    try:
        m = src_mtime()
        if os.path.exists(TRIGGER):
            if m is None:
                print("trigger present but source missing; ignoring", flush=True)
            else:
                last_published = publish(m, "manual trigger")
            os.remove(TRIGGER)
        elif m is not None and m != last_published and (time.time() - m) >= DEBOUNCE:
            last_published = publish(m, "debounced change")
    except Exception as exc:  # keep watching through transient I/O errors
        print(f"publish error: {exc}", flush=True)
    time.sleep(POLL)
