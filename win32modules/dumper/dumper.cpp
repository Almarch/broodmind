#include "dumper.h"
#include <cstdlib>

// bwapi-data/write and bwapi-data/read are the directories mounted back and
// forth with the host by analyze.py.
static const char *OUTPUT_PATH = "bwapi-data/write/dump.jsonl";

static std::string escape(const std::string &s) {
    std::string r;
    for (char c : s) {
        if (c == '"' || c == '\\') r += '\\';
        r += c;
    }
    return r;
}

void DumperModule::onStart() {
    BWAPI::Broodwar->setLocalSpeed(0);
    BWAPI::Broodwar->setFrameSkip(16);

    std::ifstream tin(TARGET_PATH);
    int f;
    while (tin >> f) targetFrames.insert(f);

    for (BWAPI::Player p : BWAPI::Broodwar->getPlayers()) {
        if (p && p->getType() == BWAPI::PlayerTypes::Player) {
            activePlayers.push_back(p);
        }
    }

    out.open(OUTPUT_PATH);
    out << "{\"event\":\"start\""
        << ",\"is_replay\":" << (BWAPI::Broodwar->isReplay() ? "true" : "false")
        << ",\"map\":\"" << escape(BWAPI::Broodwar->mapFileName()) << "\""
        << ",\"target_frames\":[";
    bool first = true;
    for (int t : targetFrames) {
        if (!first) out << ",";
        out << t;
        first = false;
    }
    out << "]}\n";
    out.flush();
}

void DumperModule::writePlayerFeatures(int frame, BWAPI::Player p, bool first) {
    if (!first) out << ",";
    BWAPI::Race race = p->getRace();
    int workers = 0;
    for (BWAPI::Unit u : p->getUnits()) {
        if (u && u->getType().isWorker()) ++workers;
    }
    out << "{\"id\":" << p->getID()
        << ",\"name\":\"" << escape(p->getName()) << "\""
        << ",\"race\":\"" << race.toString() << "\""
        << ",\"minerals\":" << p->minerals()
        << ",\"gas\":" << p->gas()
        << ",\"supply_used\":" << p->supplyUsed(race)
        << ",\"supply_total\":" << p->supplyTotal(race)
        << ",\"cum_minerals\":" << p->gatheredMinerals()
        << ",\"cum_gas\":" << p->gatheredGas()
        << ",\"workers\":" << workers
        << "}";
}

void DumperModule::onFrame() {
    const int frame = BWAPI::Broodwar->getFrameCount();
    if (targetFrames.find(frame) == targetFrames.end()) return;

    out << "{\"frame\":" << frame << ",\"players\":[";
    bool first = true;
    for (BWAPI::Player p : activePlayers) {
        writePlayerFeatures(frame, p, first);
        first = false;
    }
    out << "]}\n";
    out.flush();
}

void DumperModule::onEnd(bool isWinner) {
    out << "{\"event\":\"end\",\"is_winner\":"
        << (isWinner ? "true" : "false") << "}\n";
    out.close();
}
