# SO-101 Upma Robot

Windows-first SO-101 LeRobot project for calibrated upma stirring, ingredient cup pickup, spoon/stirrer pickup, tight gripper control, localhost dashboard control, and a bounded ChatGPT robot brain.

The robot moves only through calibrated poses or validated small bounded moves. Keep one hand near the robot power switch during every real movement command.

## GitHub Download And Windows Install

Clone the repository on a new Windows system:

```powershell
cd C:\Users\PBL
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git so101_kitchen_stirrer_milestone
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
```

Edit local robot config:

```powershell
notepad config.json
```

Set `robot_port` to your robot port, for example `COM7`.

Check the robot:

```powershell
mode
.\.venv\Scripts\python.exe connect_test.py
```

Full calibration and run guide:

```powershell
notepad UPMA_CALIBRATION_GUIDE.md
```

Solo-style CLI usage after editable install:

```powershell
uv pip install -e .
upma --help
upma setup --port COM7 --cameras 1 2
upma login
upma download lakshveeer/robot --repo-type dataset
upma robo --calibrate all
upma robo --teleop
upma dry-run --ingredients
upma run --ingredients
upma push-hf username/my-upma-dataset --repo-type dataset --folder .
```

Detailed Solo-style terminal flow:

```powershell
notepad SOLO_STYLE_USAGE.md
```

## Main Commands

Dry run, no movement:

```powershell
.\.venv\Scripts\python.exe upma_mode.py --dry-run --with-ingredients --yes
```

Run full upma with ingredient cup and spoon/stirrer pickup:

```powershell
.\.venv\Scripts\python.exe upma_mode.py --with-ingredients --yes --speed-scale 0.02 --cycles-multiplier 1 --pause 0.15 --low-pressure-lift-deg 6
```

Run smart tight-grip cup, stick, and stir sequence:

```powershell
.\.venv\Scripts\python.exe smart_upma_runner.py --yes --speed-scale 0.02 --pause 0.25 --stir-cycles 5 --tight -5 --open 30
```

Run localhost dashboard:

```powershell
.\.venv\Scripts\python.exe kitchen_robot_server.py --allow-movement
```

Open:

```text
http://127.0.0.1:8000
```

## ChatGPT Robot Brain

Set an OpenAI API key in your terminal. Do not put keys in code or commit them.

PowerShell:

```powershell
$env:OPENAI_API_KEY="your_new_api_key_here"
```

Command Prompt:

```cmd
set OPENAI_API_KEY=your_new_api_key_here
```

Plan only, no movement:

```powershell
.\.venv\Scripts\python.exe chatgpt_robot_brain.py "pick the cup, grab the stick tight, and stir slowly"
```

Execute the selected safe project action:

```powershell
.\.venv\Scripts\python.exe chatgpt_robot_brain.py "pick the cup, grab the stick tight, and stir slowly" --execute
```

## Publish To GitHub

See:

```powershell
notepad GITHUB_PUBLISH_COMMANDS.md
```

The `.gitignore` excludes `.venv`, `config.json`, logs, caches, camera snapshots, and `.env`.

## Original Milestone Notes

This first milestone only moves the Hugging Face LeRobot SO-101 follower arm through saved joint positions. It does not control the ESP32-S3, OLED, emergency-stop hardware, or the 360-degree stirring servo.

The goal is a small, inspectable project that can connect to the follower arm, save named poses, and replay a slow fixed sequence:

```bash
python replay_sequence.py --sequence HOME ABOVE_BOWL STIR_DEPTH LIFT PARK
```

## Setup Assumptions

- Raspberry Pi 5.
- SO-101 follower arm connected over USB.
- LeRobot is installed in the active Python environment.
- The arm has already been calibrated with LeRobot.
- The arm has free space to move and is not holding a stirrer yet.

Install dependencies only if needed:

```bash
python -m pip install -r requirements.txt
```

Create your local config:

```bash
cp config.example.json config.json
```

Edit `config.json` and set `robot_port` to the SO-101 USB device.

## Find The Robot USB Port

On Raspberry Pi/Linux, plug in the SO-101 and run:

```bash
ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

For more detail:

```bash
python -m lerobot.find_port
```

If that command is not available in your LeRobot version, compare the output of this command before and after plugging in the robot:

```bash
dmesg | tail -50
```

The two cameras usually appear as video devices such as `/dev/video0` and `/dev/video1`. The SO-101 arm should appear as a serial device such as `/dev/ttyACM0`, `/dev/ttyACM1`, or `/dev/ttyUSB0`.

## Connection Test

Run:

```bash
python connect_test.py
```

## Camera 0 And 1 Check

The config includes OpenCV camera indices `0` and `1`.

Check both cameras:

```bash
python camera_check.py
```

Save one snapshot from each camera:

```bash
python camera_check.py --save
```

Show preview windows:

```bash
python camera_check.py --preview
```

Camera frames are not attached to arm movement by default. To include cameras in LeRobot robot observations, set this in `config.json`:

```json
"enable_robot_cameras": true
```

Expected result:

- It prints the LeRobot API path in use.
- It prints `SUCCESS: robot connected.`
- It prints current joint positions such as `shoulder_pan.pos`, `elbow_flex.pos`, and `gripper.pos`.
- It disconnects cleanly.

## Save Positions

Move the arm manually or with your normal LeRobot teleoperation flow to each safe pose, then save it:

```bash
python save_position.py HOME
python save_position.py ABOVE_BOWL
python save_position.py STIR_DEPTH
python save_position.py LIFT
python save_position.py PARK
```

The script refuses unknown names unless `--force` is used:

```bash
python save_position.py EXTRA_SAFE_POSE --force
```

## Replay Positions

Validate the sequence without moving the arm:

```bash
python replay_sequence.py --dry-run
```

Replay the default sequence:

```bash
python replay_sequence.py
```

Replay an explicit sequence:

```bash
python replay_sequence.py --sequence HOME ABOVE_BOWL STIR_DEPTH LIFT PARK
```

Skip the Enter prompt only when you are ready and watching the robot:

```bash
python replay_sequence.py --yes --sequence HOME ABOVE_BOWL STIR_DEPTH LIFT PARK
```

## Pan Sweep Test

Sweep only the shoulder pan joint from its current pose:

```bash
python pan_sweep.py --degrees 15 --cycles 1
```

Dry run:

```bash
python pan_sweep.py --dry-run
```

Skip the Enter prompt only when you are ready and watching the robot:

```bash
python pan_sweep.py --yes --degrees 15 --cycles 1
```

## Arm-Only Stirring Motions

This project can repeat saved SO-101 poses for front/back or left/right stirring. It still does not control the 360-degree stirring servo.

Save the simple calibration poses:

```bash
python save_position.py UP
python save_position.py DOWN
python save_position.py LEFT
python save_position.py RIGHT
python save_position.py PARK
```

Save front/back endpoints:

```bash
python save_position.py STIR_FORWARD
python save_position.py STIR_BACK
```

Save left/right endpoints:

```bash
python save_position.py STIR_LEFT
python save_position.py STIR_RIGHT
```

Dry run front/back:

```bash
python stir_motion.py --motion front-back --cycles 3 --dry-run
```

Move front/back:

```bash
python stir_motion.py --motion front-back --cycles 3
```

Move left/right:

```bash
python stir_motion.py --motion left-right --cycles 3
```

## OpenCV Automatic Sweep Motions

This is rule-based vision, not training. It uses camera 0 and 1 to watch frame changes in the bowl area and repeats saved sweep poses. In `auto` mode, it switches between left/right and front/back when visual activity is low.

Dry run with cameras but no robot movement:

```bash
python opencv_auto_stir.py --dry-run --cycles 3
```

Run automatic sweep motions:

```bash
python opencv_auto_stir.py --motion auto --cycles 6
```

By default, the arm moves to `PARK` after the final cycle. To leave it at the last stirring pose:

```bash
python opencv_auto_stir.py --motion auto --cycles 6 --no-park
```

Force left/right only:

```bash
python opencv_auto_stir.py --motion left-right --cycles 6
```

Force front/back only:

```bash
python opencv_auto_stir.py --motion front-back --cycles 6
```

Use preview windows:

```bash
python opencv_auto_stir.py --preview --motion auto --cycles 6
```

## Live Camera-Guided RL-Style Stirring

This mode does not require saved poses. It captures the current robot position as the center and learns which small relative action creates the most visual activity in the camera ROI. It is bounded and rule-based: it does not train a neural network and it does not allow unbounded motion.

Dry run:

```bash
python live_rl_stir.py --dry-run --steps 10
```

Run live control:

```bash
python live_rl_stir.py --steps 20
```

Use smaller motion for first test:

```bash
python live_rl_stir.py --steps 10 --pan-deg 5 --wrist-deg 5 --lift-deg 2
```

Use camera preview:

```bash
python live_rl_stir.py --preview --steps 20
```

## ChatGPT API Robot Brain

Do not put your API key in code. Set it as an environment variable.

PowerShell:

```powershell
$env:OPENAI_API_KEY="your_new_api_key_here"
```

Dry run. This calls the OpenAI API but does not move the robot:

```bash
python chatgpt_brain.py --dry-run --steps 3
```

First real safe test:

```bash
python chatgpt_brain.py --steps 5 --pan-deg 5 --wrist-deg 5 --lift-deg 2
```

Send a small camera image to the model every 3 steps:

```bash
python chatgpt_brain.py --steps 5 --send-image-every 3
```

The model can only choose from a fixed action list. The script validates the action before moving and keeps motion bounded around the starting pose.

Let ChatGPT choose direct relative joint deltas, still validated by the script:

```bash
python chatgpt_brain.py --free-delta --wide --steps 5 --send-image-every 1
```

## Upma Mode And Localhost Dashboard

Upma mode uses the saved SO-101 LeRobot poses to run a guided cooking sequence. The robot stirs and parks the arm; a human must add ingredients and control the stove.

Dataset reference:

```text
https://huggingface.co/datasets/lakshveeer/robot
```

Dry run the full upma sequence:

```bash
python upma_mode.py --dry-run --yes
```

Run the guided real sequence only when the robot is clear and supervised:

```bash
python upma_mode.py
```

Start the localhost dashboard in dry-run-only mode:

```bash
python kitchen_robot_server.py
```

Open:

```text
http://127.0.0.1:8000
```

To allow the dashboard to start real robot movement, explicitly opt in:

```bash
python kitchen_robot_server.py --allow-movement
```

## Manual Control

Manual control does not use ChatGPT, cameras, or automatic decisions.

```bash
python manual_control.py
```

Commands:

```text
a  pan left
d  pan right
w  wrist forward
s  wrist back
r  lift up
f  lift down
c  return to start center
p  stop/relax now
q  quit
```

## Calibration Check

Use the official LeRobot tools first. Common commands are:

```bash
lerobot-calibrate --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=kitchen_stirrer_follower
```

Then run:

```bash
python connect_test.py
```

LeRobot stores robot calibration under the Hugging Face/LeRobot cache for the configured robot id. If `connect_test.py` prompts for calibration, the calibration file is missing or does not match the motor calibration.

## Safety Warnings

- Keep one hand near the arm power switch.
- Keep the bowl area empty during this milestone.
- Do not attach the stirring servo or utensil yet.
- Start with `speed_scale` at `0.2`.
- This project accepts `speed_scale` values up to `10.0`, while still capping each individual joint step to avoid sudden large commands.
- `replay_sequence.py` refuses to move if any named position is `null`.
- Press `Ctrl+C` for keyboard emergency stop.
- If movement looks wrong, cut power first, then debug software.

## If The Robot Does Not Move

1. Confirm the arm has power.
2. Confirm `config.json` uses the serial device, not a camera device.
3. Run `ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null` and update `robot_port`.
4. Run `python connect_test.py` and check whether joint positions print.
5. Check calibration with the official `lerobot-calibrate` command.
6. Confirm no other LeRobot process is already using the same USB port.
7. Try unplugging and reconnecting the USB cable, then check `dmesg | tail -50`.
