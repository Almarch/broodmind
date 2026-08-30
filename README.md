# 🚧 This is a work in progress

# BroodMind 

<img width="70" align="right" alt="broodmind" src="https://github.com/user-attachments/assets/3d250936-9769-495d-a67e-0e8a08e9596e" />

An AI learning to control the Swarm using reinforcement learning.

<details><summary>Play BroodWar v1.16.1</summary>
</br>

Blizzard officially made free StarCraft BroodWar, however the remaining challenge is to have it running on a modern computer.

Especially, the whole AI competition ecosystem is built upon the canonical v1.16.1, which is no longer distributed.

A portable version of SCBW v1.16.1 may be found on [archive.org](https://archive.org/details/sc-classic-installer_202311). Rename `StarCraft ( Click here ).exe` to `StarCraft.exe`.

On a Linux x86 platform, use [Chaoslauncher](https://github.com/MasterOfChaos/Chaoslauncher):

```sh
wine /path/to/the/game/Starcraft\ Brood\ War/Chaoslauncher.exe
```

Define the path to `StarCraft.exe` from the Settings tab, activate W-MODE 1.02 and launch the game.

Having a working SCBW version is especially important to watch replays and follow the progression of the bot.

</details>

## Set up the work station

### Build `sc-docker`

Clone the `sc-docker` repository from the [Basil-Ladder](https://github.com/basil-ladder/sc-docker) fork:

```bash
git clone https://github.com/basil-ladder/sc-docker
```

The build script tries to download the game from `http://files.theabyss.ru/sc/starcraft.zip`, a host that no longer resolves. From the [archive.org](https://archive.org/details/sc-classic-installer_202311) portable game version, the file should be formatted in the expected form, zipped and positionned in the appropriate folder:

```bash
cd /path/to/game/files/starcraft
zip -r /path/to/repo/sc-docker/scbw/local_docker/starcraft.zip .
```

The archive contains the exact following arborescence:

<details><summary><code>starcraft.zip</code></summary>

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

</details>
</br>

Build all images using the `build_images.sh` helper:

```bash
cd /path/to/sc-docker/docker
./build_images.sh 2>&1 | tee /tmp/build.log
```

Finally, create a dedicated docker network:

```bash
docker network create sc_net
```

### Install the Python wrapper

Install the Python wrapper in a virtual environment:

```bash
conda create -n bw python=3.10 -y
conda activate bw
cd /path/to/sc-docker
python -m pip install .
```

Fetch all maps and the BWTA caches:

```bash
scbw.play --install
```

This populates `~/.scbw/` with the SSCAI map pack, the 2019 season maps and the BWTA
caches. These come from GitHub Releases and are still available.


### Running games

Bots are resolved through `http://sscaitournament.com/api/bots.php`, downloaded on demand
into `~/.scbw/bots/`, then mounted as volumes. Nothing bot-related lives inside the images,
so iterating on a bot never requires a rebuild.

To launch a game:

```bash
conda activate bw
scbw.play --bots "Stardust" "PurpleWave" --map "sscai/(2)Benzene.scx" --headless --game_speed 0
```

Launching [Stardust](https://github.com/bmnielsen/Stardust) versus [PurpleWave](https://github.com/dgant/PurpleWave) in this illustrative example.

Results, logs and replays land in `~/.scbw/games/GAME_XXXXXXXX/`. To watch a replay in a native (non-dockerized) StarCraft installation:

```bash
mkdir -p "/path/to/StarCraft/maps/replays"
cp ~/.scbw/games/GAME_XXXXXXXX/player_0.rep "/path/to/the/game/Starcraft\ Brood\ War/maps/replays/"
```

The map used for the game must also be present in `/path/to/the/game/Starcraft\ Brood\ War/maps/sscai/`

## Step 1 - Train the critic

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
python play.py --cpu 16 --games 64 --seed 42 --elo-min 2300
cd ..
```

### Extract the features from selected frames

The dumper module has to be built:

```bash
make win32builder
make dumper
make clean
make bwapi
make install
```

## Step 2 - Train the actor

## License

The license is MIT with an added condition that forks may not be submitted to StarCraft AI competitions without written consent of the author.
