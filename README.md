# PBL SO-101 CLI

Solo-style Windows CLI for LeRobot SO-101 arms. It focuses on robot setup, motor IDs, calibration, teleoperation, recording, training, replay/inference, Hugging Face upload/download, Rerun viewing, and a terminal camera agent.

This is a general robot workflow. The main command is `pbl`.

## Install

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

If the folder already exists:

```cmd
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
git pull
.venv\Scripts\activate
uv pip install -e .
pbl --help
```

## Configure

```cmd
pbl setup --port COM7 --leader-port COM8 --leader-id 1 --follower-id 2 --cameras 0 1 2
pbl status
```

Check USB/COM ports:

```cmd
mode
pbl setup-usb
```

## Motor Setup And Calibration

Assign motor IDs:

```cmd
pbl setup-motors --device all
pbl robo --setup-motors all
```

Calibrate:

```cmd
pbl calibrate --device all --leader-port COM8 --follower-port COM7
pbl robo --calibrate all --leader-port COM8 --follower-port COM7
```

## Teleoperation

Fast teleop without cameras:

```cmd
pbl teleop --leader-port COM8 --follower-port COM7 --camera-mode no
```

Ask whether to use cameras:

```cmd
pbl teleop --leader-port COM8 --follower-port COM7
```

Teleop with cameras and Rerun:

```cmd
pbl teleop --leader-port COM8 --follower-port COM7 --camera-mode yes --camera-fps 30 --rerun
```

Rerun viewer: https://rerun.io/

## Record, Train, Replay

Episode recording:

```cmd
pbl robo --record --camera-mode yes --camera-fps 30 --rerun
```

No prompts:

```cmd
pbl robo --record --episodes 5 --seconds 20 --fps 60 --camera-mode yes --camera-fps 30 --rerun -y
```

Train/refine a replay policy:

```cmd
pbl robo --train --input recordings/latest --model-out models/latest_policy.json
```

Replay/inference:

```cmd
pbl robo --inference --policy models/latest_policy.json --speed-scale 0.02
pbl robo --replay
```

Record and push to Hugging Face:

```cmd
pbl robo --record --episodes 5 --seconds 20 --camera-mode yes --rerun --push-hf --repo-id YOUR_USERNAME/my-so101-recording
```

## Terminal Agent

Set the API key in the terminal, not in code:

```cmd
set OPENAI_API_KEY=your_api_key_here
```

Ask the robot what to do:

```cmd
pbl agent
```

Run a camera-guided task:

```cmd
pbl agent "move the object to the left side" --execute --steps 12
```

The agent is request-driven. It uses camera frames and small bounded robot moves from the current pose: pan, lift, elbow, wrist, wrist roll, open/close gripper, hold, done, or stop. It does not depend on kitchen poses.

## Hugging Face

```cmd
pbl login
pbl whoami
pbl download lakshveeer/robot --repo-type dataset
pbl push-hf YOUR_USERNAME/my-dataset --repo-type dataset --folder recordings/latest
pbl logout
```

## Utility

```cmd
pbl test
pbl list
pbl stop
```

GitHub Pages docs:

```text
https://lakshveerrao.github.io/kichen-robot/
```
