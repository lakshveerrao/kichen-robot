# PBL CLI Usage

This project installs a terminal command named `pbl`.

It works like a small robot CLI for this SO-101 kitchen robot project. It does not require Solo CLI:

- setup
- status
- motor ID assignment
- calibration
- teleoperation
- pose saving
- dry runs
- ingredient pickup
- stirring
- full robot run
- ChatGPT brain
- Hugging Face download/upload
- dashboard

## 1. Download On A New Windows System

Open Command Prompt.

```cmd
cd C:\Users\PBL
git clone https://github.com/lakshveerrao/kichen-robot.git so101_kitchen_stirrer_milestone
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
```

If the folder already exists:

```cmd
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
git pull
```

## 2. Install

```cmd
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install uv
uv pip install -e .
```

Check:

```cmd
pbl --help
```

`upma --help` also works as an old alias, but use `pbl` from now on.

## 3. Configure Robot

No commas for cameras. Use spaces:

```cmd
pbl setup --port COM7 --cameras 1 2
```

If you have a leader arm on `COM8` for teleoperation:

```cmd
pbl setup --port COM7 --leader-port COM8 --leader-id 1 --follower-id kitchen_stirrer_follower --cameras 1 2
```

Check robot connection:

```cmd
pbl status
```

Check Windows ports manually:

```cmd
mode
```

## 4. Assign Motor IDs

Only do this for a new robot or after replacing motors. LeRobot will ask you to connect only one motor at a time.

```cmd
pbl setup-motors --device all
```

Follower only:

```cmd
pbl setup-motors --device follower --follower-port COM7
```

Same command through `robo`:

```cmd
pbl robo --setup-motors all
```

## 5. Calibrate

Calibrate follower only:

```cmd
pbl calibrate --device follower --follower-port COM7
```

Calibrate leader and follower:

```cmd
pbl calibrate --device all --leader-port COM8 --follower-port COM7
```

Same command through `robo`:

```cmd
pbl robo --calibrate all --leader-port COM8 --follower-port COM7
```

## 6. Teleoperation

Local teleoperation does not require Solo CLI:

```cmd
pbl teleop
```

It asks whether you want cameras. Camera capture runs in background threads so teleop stays fast.

With explicit ports:

```cmd
pbl teleop --leader-port COM8 --follower-port COM7 --leader-id 1 --follower-id kitchen_stirrer_follower
```

Skip cameras:

```cmd
pbl teleop --leader-port COM8 --follower-port COM7 --camera-mode no
```

Use configured cameras without asking:

```cmd
pbl teleop --leader-port COM8 --follower-port COM7 --camera-mode yes --camera-fps 30
```

Teleop with camera prompt:

```cmd
pbl teleop --leader-port COM8 --follower-port COM7
```

Teleop with Rerun camera view and robot data:

```cmd
pbl teleop --leader-port COM8 --follower-port COM7 --camera-mode yes --camera-fps 30 --rerun
```

Rerun viewer: https://rerun.io/

Use teleop to move the robot to each pose, then save the pose.

## 7. Save Poses

Move the robot first, then save only that pose.

Main poses:

```cmd
pbl save-pose HOME
pbl save-pose ABOVE_BOWL
pbl save-pose STIR_DEPTH
pbl save-pose LIFT
pbl save-pose PARK
pbl save-pose STIR_FORWARD
pbl save-pose STIR_BACK
pbl save-pose STIR_LEFT
pbl save-pose STIR_RIGHT
pbl save-pose UP
pbl save-pose DOWN
pbl save-pose LEFT
pbl save-pose RIGHT
```

Ingredient cup poses:

```cmd
pbl save-pose CUP_APPROACH
pbl save-pose CUP_GRASP
pbl save-pose CUP_LIFT
pbl save-pose CUP_POUR
pbl save-pose CUP_PLACE
pbl save-pose CUP_RELEASE
```

Spoon/stick poses:

```cmd
pbl save-pose STIRRER_APPROACH
pbl save-pose STIRRER_GRASP
pbl save-pose STIRRER_LIFT
pbl save-pose STIRRER_READY
```

## 8. Validate Without Movement

```cmd
pbl dry-run
pbl dry-run --ingredients
```

## 9. Test Small Real Movements

```cmd
pbl stir --motion front-back --cycles 1
pbl stir --motion left-right --cycles 1
pbl ingredients --action all
```

## 10. Run The Robot

Run normal upma stirring:

```cmd
pbl run
```

Run with ingredient cup and spoon/stick pickup:

```cmd
pbl run --ingredients
```

If camera check blocks movement and you are watching the robot yourself:

```cmd
pbl run --ingredients --skip-camera-check
```

Smart tight-grip cup, stick, stir:

```cmd
pbl smart --cycles 5 --tight -5 --open 30
```

Grip and move down:

```cmd
pbl grip-down --tight -5
```

## 11. Dashboard

Dry-run dashboard:

```cmd
pbl dashboard
```

Real movement dashboard:

```cmd
pbl dashboard --allow-movement
```

Open:

```text
http://127.0.0.1:8000
```

## 12. ChatGPT Brain

Command Prompt:

```cmd
set OPENAI_API_KEY=your_new_api_key_here
pbl brain "pick the cup, grab the stick tight, and stir slowly"
pbl brain "pick the cup, grab the stick tight, and stir slowly" --execute
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="your_new_api_key_here"
pbl brain "pick the cup, grab the stick tight, and stir slowly"
pbl brain "pick the cup, grab the stick tight, and stir slowly" --execute
```

## 13. Hugging Face

Login:

```cmd
pbl login
pbl whoami
```

Download:

```cmd
pbl download lakshveeer/robot --repo-type dataset
```

Upload dataset/project folder:

```cmd
pbl push-hf username/my-upma-dataset --repo-type dataset --folder .
```

## 14. Automatic Agent Controller

Set your OpenAI API key in the terminal, not in code:

```cmd
set OPENAI_API_KEY=your_api_key_here
```

Start the dashboard:

```cmd
pbl dashboard --allow-movement
```

Terminal-only agent:

```cmd
pbl agent
```

It asks what it should do. To run pen-to-cup without saved poses, use camera-guided bounded micro-moves:

```cmd
pbl agent "pick up the pen and place it in the cup" --execute --steps 12
```

This does not require saving poses. The robot only uses small bounded moves from its current position: pan, lift, wrist, open gripper, close gripper, hold, done, or stop.

Optional saved-pose mode:

```cmd
pbl save-pose PEN_APPROACH --force
pbl save-pose PEN_GRASP --force
pbl save-pose PEN_LIFT --force
pbl save-pose CUP_TARGET --force
pbl save-pose PEN_RELEASE --force
pbl save-pose PEN_RETREAT --force
pbl agent "pick up the pen and place it in the cup" --execute --use-saved-poses
```

The agent uses cameras and ChatGPT, but it only runs bounded project actions. It does not invent raw joint angles.

## 15. Record, Train, Inference, Replay

This PBL CLI does not depend on Solo CLI. Recording is episode-based, similar to LeRobot data collection demos. If you do not pass `--episodes` or `--seconds`, it asks you:

```cmd
pbl robo --record --camera-mode yes --camera-fps 30 --rerun
```

It asks:

- how many episodes you want to record
- how many seconds each episode should be

Non-interactive recording:

```cmd
pbl robo --record --episodes 5 --seconds 20 --fps 60 --camera-mode yes --camera-fps 30 --rerun -y
```

Record and push the dataset to Hugging Face:

```cmd
pbl robo --record --episodes 5 --seconds 20 --camera-mode yes --rerun --push-hf --repo-id YOUR_USERNAME/my-so101-recording
```

Train/refine means building a replay policy from the recorded episodes. Replay/inference means playing that policy back on the robot:

```cmd
pbl robo --train --input recordings/latest --model-out models/latest_policy.json
pbl robo --inference --policy models/latest_policy.json --speed-scale 0.02
pbl robo --replay
```

`record` saves `recordings/latest/episode_000000/observations.jsonl`, camera snapshots, and `manifest.json`. `train` builds a replay policy JSON from those episodes. `inference` plays that policy safely through `move_to_position`. `replay` uses this project's local saved-pose replay.

Record with camera metadata and latest camera images:

```cmd
pbl robo --record --episodes 1 --seconds 20 --fps 60 --camera-mode yes --camera-fps 30
```

Record with live Rerun camera/data logging:

```cmd
pbl robo --record --episodes 1 --seconds 20 --fps 60 --camera-mode yes --camera-fps 30 --rerun
```

## 16. Stop

```cmd
pbl stop
```

If this returns access denied, close the running robot terminal or use the physical robot power switch.
