#!/usr/bin/env bash
set -u

export WINEPREFIX=/home/starcraft/.wine
export WINEARCH=win32
export DISPLAY=:99

REPLAY="${REPLAY:?REPLAY env not set}"          # e.g. 0a9c02acedea4d3b.rep
TIMEOUT_S="${TIMEOUT_S:-900}"

LOG() { echo "$(date +%Y-%m-%dT%H:%M:%S)" "$@"; }

# Xvfb on a per-container display (containers have isolated namespaces, so a
# single display number never collides across parallel runs).
Xvfb :99 -screen 0 640x480x24 > /app/logs/xvfb.log 2>&1 &
sleep 3

# Rewrite the baked bwapi.ini so this run loads the requested replay.
BWAPI_INI="$BWAPI_DATA_DIR/bwapi.ini"
sed -i "s:^map = maps/replays/.*:map = maps/replays/$REPLAY:" "$BWAPI_INI"

# The .rep is bind-mounted read-only at maps/replays/<REPLAY>.
[ -f "$MAP_DIR/replays/$REPLAY" ] || { LOG "replay not found: $REPLAY"; exit 1; }

DUMP="$BOT_DATA_WRITE_DIR/dump.jsonl"
rm -f "$DUMP"

LOG "launching headful Starcraft with replay $REPLAY"
pushd "$SC_DIR" > /dev/null
wine "$SC_DIR/bwheadless.exe" \
    -l "$BWAPI_DATA_DIR/BWAPI.dll" \
    -e "$SC_DIR/StarCraft.exe" \
    --installpath "$SC_DIR" \
    --headful > /app/logs/starcraft.log 2>&1 &
SCPID=$!
popd > /dev/null

# Wait for the dumper to signal completion via its end event.
deadline=$(( $(date +%s) + TIMEOUT_S ))
while [ "$(date +%s)" -lt "$deadline" ]; do
    if grep -q '"event":"end"' "$DUMP" 2>/dev/null; then
        LOG "replay finished, features dumped"
        break
    fi
    if ! kill -0 $SCPID 2>/dev/null; then
        LOG "Starcraft exited before end event"
        break
    fi
    sleep 1
done

[ -f "$DUMP" ] && LOG "dump lines: $(wc -l < "$DUMP")" || LOG "no dump produced"

kill -9 $SCPID 2>/dev/null
wineserver -k 2>/dev/null
kill -9 $(pgrep -x Xvfb) 2>/dev/null
LOG "done"
exit 0
