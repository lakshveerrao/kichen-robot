# PBL CLI Usage

This project installs a terminal command named `pbl`.

It works like a small Solo-style robot CLI for this SO-101 kitchen robot project:

- setup
- status
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

Check robot connection:

```cmd
pbl status
```

Check Windows ports manually:

```cmd
mode
```

## 4. Calibrate

Calibrate follower only:

```cmd
pbl calibrate --port COM7
```

Solo-style full calibration, if Solo CLI is installed:

```cmd
pbl robo --calibrate all
```

## 5. Teleoperation

If Solo CLI is installed:

```cmd
pbl teleop
```

or:

```cmd
pbl robo --teleop
```

Use teleop to move the robot to each pose, then save the pose.

## 6. Save Poses

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

## 7. Validate Without Movement

```cmd
pbl dry-run
pbl dry-run --ingredients
```

## 8. Test Small Real Movements

```cmd
pbl stir --motion front-back --cycles 1
pbl stir --motion left-right --cycles 1
pbl ingredients --action all
```

## 9. Run The Robot

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

## 10. Dashboard

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

## 11. ChatGPT Brain

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

## 12. Hugging Face

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

## 13. Solo Pass-Through Commands

These require Solo CLI installed:

```cmd
pbl robo --record
pbl robo --train
pbl robo --inference
pbl robo --replay
```

## 14. Stop

```cmd
pbl stop
```

If this returns access denied, close the running robot terminal or use the physical robot power switch.
