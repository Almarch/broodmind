# Host-side build entry point. Runs the win32 build container.

IMAGE   := win32builder
MODULES := win32modules

.PHONY: image dumper clean

win32builder:
	docker build -t $(IMAGE) -f $(MODULES)/win32builder.Dockerfile $(MODULES)/

dumper:
	mkdir -p $(MODULES)/dumper/dist
	docker run --rm \
		-v $(PWD)/$(MODULES):/src \
		-v $(PWD)/$(MODULES)/dumper/dist:/out \
		$(IMAGE) make -C dumper

clean:
	docker run --rm \
		-v $(PWD)/$(MODULES):/src \
		$(IMAGE) rm -rf /src/dumper/build /src/dumper/dist

BOT_DIR := $(HOME)/.scbw/bots/dumper

.PHONY: bwapi install

# BWAPI.dll ships inside the official release already fetched by the image.
bwapi:
	mkdir -p $(MODULES)/dumper/dist
	docker run --rm \
		-v $(PWD)/$(MODULES)/dumper/dist:/out \
		$(IMAGE) cp /opt/bwapi/Release_Binary/Starcraft/bwapi-data/BWAPI.dll /out/

install: dumper bwapi
	mkdir -p $(BOT_DIR)/AI $(BOT_DIR)/read $(BOT_DIR)/write
	cp $(MODULES)/dumper/dist/dumper.dll $(BOT_DIR)/AI/
	cp $(MODULES)/dumper/dist/BWAPI.dll  $(BOT_DIR)/
	cp $(MODULES)/dumper/bot.json        $(BOT_DIR)/