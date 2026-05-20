# PBL CLI Usage

`pbl` is a Solo-style SO-101 robot CLI. It does not require Solo CLI and it is built around general robot operations.

Main areas:

- setup
- status/test
- motor ID assignment
- calibration
- teleoperation
- recording
- train/refine replay policies
- inference/replay
- terminal camera agent
- Hugging Face download/upload
- local asset listing
- stop robot processes

## 1. Install

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

## 2. Configure

```cmd
pbl setup --port COM7 --leader-port COM8 --leader-id 1 --follower-id 2 --cameras 0 1 2
pbl status
mode
pbl setup-usb
```

## 3. Motor IDs

```cmd
pbl setup-motors --device all
pbl robo --setup-motors all
```

## 4. Calibration

```cmd
pbl calibrate --device all --leader-port COM8 --follower-port COM7
pbl robo --calibrate all --leader-port COM8 --follower-port COM7
```

## 5. Teleop

```cmd
pbl teleop --leader-port COM8 --follower-port COM7 --camera-mode no
pbl teleop --leader-port COM8 --follower-port COM7
pbl teleop --leader-port COM8 --follower-port COM7 --camera-mode yes --camera-fps 30 --rerun
```

## 6. Record

Interactive episode recording:

```cmd
pbl robo --record --camera-mode yes --camera-fps 30 --rerun
```

No prompts:

```cmd
pbl robo --record --episodes 5 --seconds 20 --fps 60 --camera-mode yes --camera-fps 30 --rerun -y
```

Record and upload:

```cmd
pbl robo --record --episodes 5 --seconds 20 --camera-mode yes --rerun --push-hf --repo-id YOUR_USERNAME/my-so101-recording
```

## 7. Train And Replay

Train/refine a replay policy:

```cmd
pbl robo --train --input recordings/latest --model-out models/latest_policy.json
```

Replay/inference:

```cmd
pbl robo --inference --policy models/latest_policy.json --speed-scale 0.02
pbl robo --replay --policy models/latest_policy.json --speed-scale 0.02
```

## 8. Terminal Agent

Set the API key:

```cmd
set OPENAI_API_KEY=your_api_key_here
```

Ask in terminal:

```cmd
pbl agent
```

Run a request-driven camera task:

```cmd
pbl agent "move the object to the left side" --execute --steps 12
```

The agent is not hardcoded to one kitchen task. It uses camera frames and bounded moves from the current pose.

## 9. Hugging Face

```cmd
pbl login
pbl whoami
pbl download lakshveeer/robot --repo-type dataset
pbl push-hf YOUR_USERNAME/my-dataset --repo-type dataset --folder recordings/latest
pbl logout
```

## 10. Utility

```cmd
pbl test
pbl list
pbl stop
```
