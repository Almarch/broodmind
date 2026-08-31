# Starcraft replay-analysis image.
#
# Context = repository root. Derived from the ready-to-run starcraft:game image
# (built by sc-docker) that ships StarCraft: Brood War + BWAPI + Wine under
# headless X. It only adds the artefacts needed to replay an existing .rep and
# dump per-frame economy features: the bwheadless launcher (built from
# ../bwheadless), the BWAPI module loader and the dumper AIModule (built from
# ../win32modules/dumper).
#
# Build (from repo root, after `make analyze-image`):
#   docker build -t starcraft:analyze -f analyze/Dockerfile .

FROM starcraft:game

# Run as the image's own user and keep its default DISPLAY env (overridden at
# runtime by the entrypoint to a free Xvfb display local to the container).
USER starcraft

# bwheadless launcher: build output from bwheadless/ (reference, unpatched).
COPY bwheadless/build/bwheadless_ref.exe /test/bwheadless.exe

# BWAPI loader + dumper AIModule: dist output from win32modules/dumper.
COPY win32modules/dumper/dist/BWAPI.dll  /app/sc/bwapi-data/BWAPI.dll
COPY win32modules/dumper/dist/dumper.dll /app/sc/bwapi-data/AI/dumper.dll

# Rewritable bwapi.ini template, patched per-run by the entrypoint.
COPY analyze/bwapi.ini /app/sc/bwapi-data/bwapi.ini

# Orchestrates Xvfb + headful replay playback + feature collection.
COPY analyze/entrypoint.sh /app/analyze_entrypoint.sh

ENTRYPOINT ["/app/analyze_entrypoint.sh"]
