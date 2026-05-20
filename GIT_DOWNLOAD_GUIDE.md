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
pbl robo --record --camera-mode yes --camera-fps 30 --rerun
pbl robo --record --episodes 5 --seconds 20 --fps 60 --camera-mode yes --camera-fps 30 --rerun -y
pbl robo --record --episodes 5 --seconds 20 --camera-mode yes --rerun --push-hf --repo-id YOUR_USERNAME/my-so101-recording
pbl robo --train
pbl robo --inference --speed-scale 0.02
```

Without `--episodes` or `--seconds`, the recorder asks how many episodes and how many seconds per episode.

If you have a leader arm on `COM8` for teleoperation:

```cmd
pbl setup --port COM7 --leader-port COM8 --leader-id 1 --follower-id kitchen_stirrer_follower --cameras 1 2
pbl teleop
pbl teleop --leader-port COM8 --follower-port COM7 --camera-mode no
pbl teleop --leader-port COM8 --follower-port COM7
pbl teleop --leader-port COM8 --follower-port COM7 --camera-mode yes --camera-fps 30
pbl teleop --leader-port COM8 --follower-port COM7 --camera-mode yes --camera-fps 30 --rerun
```

Rerun camera/data viewer: https://rerun.io/

## Main Run Commands

```cmd
pbl dry-run --ingredients
pbl run --ingredients
pbl smart --cycles 5 --tight -5 --open 30
pbl dashboard --allow-movement
```

## Automatic Agent Controller

Set your OpenAI API key in the terminal, then start the dashboard:

```cmd
set OPENAI_API_KEY=your_api_key_here
pbl dashboard --allow-movement
```

Terminal-only agent:

```cmd
pbl agent
```

Pen-to-cup without saved poses:

```cmd
pbl agent "pick up the pen and place it in the cup" --execute --steps 12
```

This is not hardcoded to pen/cup. It uses camera-guided bounded micro-moves from the current robot pose for the request you type.

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
