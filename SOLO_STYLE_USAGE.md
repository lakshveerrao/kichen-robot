# Solo-Style Usage

This project installs a terminal command named `upma`, similar to how Solo installs `solo`.

## First Install

Use Command Prompt or PowerShell.

```cmd
cd C:\Users\PBL\Desktop
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git so101-upma
cd so101-upma
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install uv
uv pip install -e .
upma --help
```

If you are already inside the project folder, do not clone into the same folder again.

## Expected Help

```text
usage: upma [-h]
            {setup,status,calibrate,teleop,save-pose,dry-run,run,smart,ingredients,stir,grip-down,brain,dashboard,stop,guide}
            ...

SO-101 upma robot CLI
```

## Configure

```cmd
upma setup --port COM7 --cameras 1 2
upma status
```

## Calibrate

```cmd
upma calibrate --port COM7
```

If you have Solo CLI installed and a leader arm on COM8:

```cmd
upma teleop
```

## Save Poses

Move the robot to each pose first, then save only that pose.

```cmd
upma save-pose HOME
upma save-pose ABOVE_BOWL
upma save-pose STIR_DEPTH
upma save-pose LIFT
upma save-pose PARK
upma save-pose STIR_FORWARD
upma save-pose STIR_BACK
upma save-pose STIR_LEFT
upma save-pose STIR_RIGHT
upma save-pose UP
upma save-pose DOWN
upma save-pose LEFT
upma save-pose RIGHT
upma save-pose CUP_APPROACH
upma save-pose CUP_GRASP
upma save-pose CUP_LIFT
upma save-pose CUP_POUR
upma save-pose CUP_PLACE
upma save-pose CUP_RELEASE
upma save-pose STIRRER_APPROACH
upma save-pose STIRRER_GRASP
upma save-pose STIRRER_LIFT
upma save-pose STIRRER_READY
```

## Validate

```cmd
upma dry-run
upma dry-run --ingredients
```

## Test Movement

```cmd
upma stir --motion front-back --cycles 1
upma stir --motion left-right --cycles 1
upma ingredients --action all
```

## Run Robot

Without ingredient pickup:

```cmd
upma run
```

With ingredient cup and stick pickup:

```cmd
upma run --ingredients
```

Smart tight-grip cup, stick, stir:

```cmd
upma smart --cycles 5 --tight -5 --open 30
```

Grip and down:

```cmd
upma grip-down --tight -5
```

## ChatGPT Brain

Command Prompt:

```cmd
set OPENAI_API_KEY=your_new_api_key_here
upma brain "pick the cup, grab the stick tight, and stir slowly"
upma brain "pick the cup, grab the stick tight, and stir slowly" --execute
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="your_new_api_key_here"
upma brain "pick the cup, grab the stick tight, and stir slowly"
upma brain "pick the cup, grab the stick tight, and stir slowly" --execute
```

## Dashboard

```cmd
upma dashboard --allow-movement
```

Open:

```text
http://127.0.0.1:8000
```

## Stop

```cmd
upma stop
```
