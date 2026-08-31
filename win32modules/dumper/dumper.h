#pragma once
#include <BWAPI.h>
#include <fstream>
#include <set>
#include <vector>

// Minimal AIModule: snapshots economy features per player at a set of target
// frames during replay playback. Plays nothing.
class DumperModule : public BWAPI::AIModule {
public:
    void onStart() override;
    void onFrame() override;
    void onEnd(bool isWinner) override;

private:
    std::ofstream out;
    std::set<int> targetFrames;
    std::vector<BWAPI::Player> activePlayers;
    void writePlayerFeatures(int frame, BWAPI::Player p, bool first);
};

static const char *TARGET_PATH = "bwapi-data/read/target_frames.txt";
