# Git Download Guide

Use this on any Windows computer to download and run the PBL kitchen robot project.

## Fresh Download

```cmd
cd C:\Users\PBL
git clone https://github.com/lakshveerrao/kichen-robot.git so101_kitchen_stirrer_milestone
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install uv
uv pip install -e .
pbl --help
```

## If The Folder Already Exists

```cmd
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
git pull
.venv\Scripts\activate
uv pip install -e .
pbl --help
```

## First Robot Setup

```cmd
pbl setup --port COM7 --cameras 1 2
pbl status
```

Assign motor IDs for a new robot only:

```cmd
pbl setup-motors --device all
```

Calibrate:

```cmd
pbl calibrate --device follower --follower-port COM7
```

Local record/train/inference:

```cmd
pbl robo --record --seconds 20 --fps 10
pbl robo --record --seconds 20 --fps 60 --camera-mode yes --camera-fps 30
pbl robo --train
pbl robo --inference --speed-scale 0.02
```

If you have a leader arm on `COM8` for teleoperation:

```cmd
pbl setup --port COM7 --leader-port COM8 --leader-id 1 --follower-id kitchen_stirrer_follower --cameras 1 2
pbl teleop
pbl teleop --camera-mode no
```

## Main Run Commands

```cmd
pbl dry-run --ingredients
pbl run --ingredients
pbl smart --cycles 5 --tight -5 --open 30
pbl dashboard --allow-movement
```

## Documentation Site

Site source is in:

```cmd
docs\index.html
```

Enable GitHub Pages from repository settings:

```text
Settings -> Pages -> Deploy from a branch -> main -> /docs
```

Expected URL:

```text
https://lakshveerrao.github.io/kichen-robot/
```

## Push Changes Back To GitHub

```cmd
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
git add .
git commit -m "Update PBL kitchen robot"
git push
```

Do not upload API keys. Do not commit `.venv` or `config.json`.
