# broodmind
An AI learning to play BroodWar.


## Install sc-docker

### Clone the repository

```bash
git clone https://github.com/basil-ladder/sc-docker
cd sc-docker
```

Use the `basil-ladder` fork, not the original `Games-and-Simulations` upstream: the
former is the one maintained for the BASIL ladder and has updated Wine and Java layers.

### Provide the game files

The game has been made freely available by Blizzard, however they updated the version and BWAPI requires v1.16.1. The build script tries to download the game from `http://files.theabyss.ru/sc/starcraft.zip`, a host that no longer resolves. The appropriate version may be found on [archive.org](https://archive.org/details/sc-classic-installer_202311).

Files must sit at the archive root: 

```bash
cd /path/to/game/files/starcraft
zip -r /path/to/repo/sc-docker/scbw/local_docker/starcraft.zip .
```

The `starcraft.zip` archive contains the following arborescence:
```
.
├── Ashworld.pal
├── Attack.ani
├── AviDummy.bmp
├── Badlands.pal
├── battle.snp
├── BROODAT.MPQ
├── BroodWar.mpq
├── characters
├── Desert.pal
├── EditLocal.dll
├── Farbpalette.pal
├── Ice.pal
├── Jungle.pal
├── Local.dll
├── maps
├── Menu1.pal
├── Menu2.pal
├── Menu3.pal
├── MenuButtonsPressed.bmp
├── Menu.pal
├── patch_rt.mpq
├── Points.bmp
├── ProLoss.pal
├── ProtossHud.bmp
├── ProWin.pal
├── psapi.dll
├── ReplayHud.bmp
├── Resources.bmp
├── Riched20.dll
├── Select.ani
├── Smackw32.dll
├── Space.pal
├── standard.snp
├── StarCraft.ani
├── StarCraft.exe
├── StarCraft.mpq
├── STARDAT.MPQ
├── StarEdit.exe
├── storm.dll
├── Target1.ani
├── TerLoss.pal
├── TerranHud.bmp
├── TerWin.pal
├── TopMenu.bmp
├── Twilight.pal
├── ZergHud.bmp
├── ZergLoss.pal
└── ZergWin.pal
```

### Build the images

Build all images using the `build_images.sh` helper:

```bash
cd docker
./build_images.sh 2>&1 | tee /tmp/build.log
```

### Install the Python wrapper

Install the Python wrapper in a virtual environment:

```bash
conda create -n bw python=3.10 -y
conda activate bw
cd /path/to/sc-docker
pip install -e .
```

### Create the Docker network

`scbw` hardcodes a subnet for its `sc_net` network and has no fallback, so it fails with
`Pool overlaps with other one on this address space` if another Docker network already
occupies that range. Creating the network first lets Docker pick a free subnet, and
`ensure_local_net` then finds it by name and skips creation:

```bash
docker network create sc_net
```

### Fetch maps and BWTA caches

```bash
scbw.play --install
```

This populates `~/.scbw/` with the SSCAI map pack, the 2019 season maps and the BWTA
caches. These come from GitHub Releases and are still available.

### Optional: VNC viewer for headful mode

```bash
sudo apt install tigervnc-viewer
sudo ln -s $(which vncviewer) /usr/local/bin/vnc-viewer
```

`scbw` looks for a binary named `vnc-viewer` in `PATH`. The viewer often connects before
Wine has started the server inside the container, producing *"the connection was dropped by
the server before the session could be established"* — simply reconnect.

### Running games

Bots are resolved through `http://sscaitournament.com/api/bots.php`, downloaded on demand
into `~/.scbw/bots/`, then mounted as volumes. Nothing bot-related lives inside the images,
so iterating on a bot never requires a rebuild.

To launch a game:

```bash
conda activate bw
scbw.play --bots "Stardust" "PurpleWave" --map "sscai/(2)Benzene.scx" --headless --game_speed 0
```

Launching [Stardust](https://github.com/bmnielsen/Stardust) versus [PurpleWave](https://github.com/dgant/PurpleWave).

`--game_speed` is BWAPI's `local_speed`, in milliseconds per frame: `0` runs as fast as the
CPU allows (the working mode for batch evaluation), `42` matches the *fastest* competitive
speed and is what you want when watching over VNC.

To watch a game instead of running it headless:

```bash
scbw.play --bots "Stardust" "PurpleWave" --map "sscai/(2)Benzene.scx" --show_all --game_speed 42
```

In headful mode the map has to be selected manually in the lobby — a known
*"Unable to distribute map"* bug. Create the game and the bots join on their own.

### Viewing a replay

Results, logs and replays land in `~/.scbw/games/GAME_XXXXXXXX/`. To watch a replay in a
native (non-dockerized) StarCraft installation:

```bash
mkdir -p "/path/to/StarCraft/maps/replays"
cp ~/.scbw/games/GAME_XXXXXXXX/player_0.rep "/path/to/StarCraft/maps/replays/"
```

The map used for the game must also be present in the native installation.

## Step 1 - supervised learning

### Generate parties between existing bots

First of all an inventory of all available bots and maps must be produced:
```bash
cd inventory
python inventorize.py
cd ..
```

Then, a set of parties can be launched:

```bash
cd play
python play.py --cpu 16 --games 128 --elo-min 2500 --seed 42
cd ..
```

### Extract the features from selected frames

The dumper module has to be built:

```bash
make win32builder
make dumper
make clean
```

## License

The license is MIT with an added condition that forks may not be submitted to StarCraft AI competitions without written consent of the author.
