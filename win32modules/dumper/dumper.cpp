#include "dumper.h"

// bwapi-data/write is the only directory mounted back to the host.
static const char *OUTPUT_PATH = "bwapi-data/write/dump.jsonl";

void DumperModule::onStart() {
    BWAPI::Broodwar->setLocalSpeed(0);
    BWAPI::Broodwar->setFrameSkip(16);
    out.open(OUTPUT_PATH);
    out << "{\"event\":\"start\""
        << ",\"is_replay\":" << (BWAPI::Broodwar->isReplay() ? "true" : "false")
        << ",\"map\":\"" << BWAPI::Broodwar->mapFileName() << "\""
        << ",\"players\":" << BWAPI::Broodwar->getPlayers().size()
        << "}\n";
    out.flush();
}

void DumperModule::onFrame() {
    const int frame = BWAPI::Broodwar->getFrameCount();
    if (frame % SAMPLE_PERIOD != 0) return;

    out << "{\"frame\":" << frame
        << ",\"units\":" << BWAPI::Broodwar->getAllUnits().size()
        << "}\n";
}

void DumperModule::onEnd(bool isWinner) {
    out << "{\"event\":\"end\",\"is_winner\":"
        << (isWinner ? "true" : "false") << "}\n";
    out.close();
}