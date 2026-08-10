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