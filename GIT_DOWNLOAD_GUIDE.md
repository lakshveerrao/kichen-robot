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

If you have a leader arm on `COM8` for teleoperation:

```cmd
pbl setup --port COM7 --leader-port COM8 --leader-id 1 --follower-id kitchen_stirrer_follower --cameras 1 2
pbl teleop
```

## Main Run Commands

```cmd
pbl dry-run --ingredients
pbl run --ingredients
pbl smart --cycles 5 --tight -5 --open 30
pbl dashboard --allow-movement
```

## Push Changes Back To GitHub

```cmd
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
git add .
git commit -m "Update PBL kitchen robot"
git push
```

Do not upload API keys. Do not commit `.venv` or `config.json`.
