#include <BWAPI.h>
#include <windows.h>
#include "dumper.h"

extern "C" __declspec(dllexport) void gameInit(BWAPI::Game *game) {
    BWAPI::BroodwarPtr = game;
}

extern "C" __declspec(dllexport) BWAPI::AIModule *newAIModule() {
    return new DumperModule();
}

BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID) { return TRUE; }