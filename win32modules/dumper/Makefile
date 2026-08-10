# Build a 32-bit BWAPI 4.4.0 AIModule with MSVC under Wine.
# Run from the repository root:
#   docker run --rm -v $PWD/win32modules:/src \
#              -v ~/.scbw/bots/dumper/AI:/out win32builder make -C dumper

BWAPI_ROOT ?= /opt/bwapi/Release_Binary
OUT_DIR    ?= /out
BUILD_DIR  := build

CXXFLAGS := /nologo /EHsc /MD /O2 /W3 /std:c++14 \
            /D_CRT_SECURE_NO_WARNINGS /DNOMINMAX /DWIN32 /D_WINDOWS \
            /I$(BWAPI_ROOT)/include

# BWAPI ships BWAPILIB as sources, not as a prebuilt import library.
LIB_SRC := $(wildcard $(BWAPI_ROOT)/BWAPILIB/Source/*.cpp) \
           $(BWAPI_ROOT)/BWAPILIB/UnitCommand.cpp
LIB_OBJ := $(patsubst %.cpp,$(BUILD_DIR)/bwapilib/%.obj,$(notdir $(LIB_SRC)))

MOD_SRC := dumper.cpp dll_main.cpp
MOD_OBJ := $(patsubst %.cpp,$(BUILD_DIR)/%.obj,$(MOD_SRC))

TARGET := $(OUT_DIR)/dumper.dll

all: $(TARGET)

$(BUILD_DIR)/bwapilib/%.obj: $(BWAPI_ROOT)/BWAPILIB/Source/%.cpp
	@mkdir -p $(dir $@)
	cl $(CXXFLAGS) /c $< /Fo$@

$(BUILD_DIR)/bwapilib/UnitCommand.obj: $(BWAPI_ROOT)/BWAPILIB/UnitCommand.cpp
	@mkdir -p $(dir $@)
	cl $(CXXFLAGS) /c $< /Fo$@

$(BUILD_DIR)/bwapilib.lib: $(LIB_OBJ)
	lib /nologo /OUT:$@ $^

$(BUILD_DIR)/%.obj: %.cpp
	@mkdir -p $(dir $@)
	cl $(CXXFLAGS) /c $< /Fo$@

$(TARGET): $(MOD_OBJ) $(BUILD_DIR)/bwapilib.lib
	@mkdir -p $(OUT_DIR)
	link /nologo /DLL /OUT:$@ $(MOD_OBJ) $(BUILD_DIR)/bwapilib.lib

clean:
	rm -rf $(BUILD_DIR)

.PHONY: all clean
