#pragma once
#include <BWAPI.h>
#include <fstream>

// Minimal AIModule: writes one line per sampled frame, plays nothing.
class DumperModule : public BWAPI::AIModule {
public:
    void onStart() override;
    void onFrame() override;
    void onEnd(bool isWinner) override;

private:
    std::ofstream out;
    static const int SAMPLE_PERIOD = 72;  // ~3 seconds at fastest speed
};
