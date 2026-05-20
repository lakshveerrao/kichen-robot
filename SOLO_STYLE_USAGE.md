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
            {setup,status,calibrate,teleop,robo,save-pose,dry-run,run,smart,ingredients,stir,grip-down,brain,dashboard,stop,guide,login,whoami,download,push-hf}
            ...

SO-101 upma robot CLI
```

## Configure

```cmd
upma setup --port COM7 --cameras 1 2
upma status
```

## Hugging Face Login And Downloads

Log in:

```cmd
upma login
upma whoami
```

Download a dataset/model from Hugging Face:

```cmd
upma download lakshveeer/robot --repo-type dataset
upma download username/model-name --repo-type model --local-dir downloads\model-name
```

## Calibrate

```cmd
upma calibrate --port COM7
```

Solo-style robot commands:

```cmd
upma robo --calibrate all
upma robo --calibrate follower --port COM7
```

If you have Solo CLI installed and a leader arm on COM8:

```cmd
upma teleop
upma robo --teleop
upma robo --teleop -y
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

## Start The Robot Dashboard

Dry-run only dashboard:

```cmd
upma dashboard
```

Real movement dashboard:

```cmd
upma dashboard --allow-movement
```

Open:

```text
http://127.0.0.1:8000
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

## Recording, Training, Inference, Replay

These commands pass through to Solo CLI if Solo is installed in the environment:

```cmd
upma robo --record
upma robo --record --yes
upma robo --train
upma robo --inference
upma robo --replay
```

Use the local calibrated workflow for this project's direct cooking motions:

```cmd
upma dry-run --ingredients
upma run --ingredients
upma smart --cycles 5 --tight -5 --open 30
```

## Push To Hugging Face

Upload this project or a dataset folder:

```cmd
upma push-hf username/my-upma-dataset --repo-type dataset --folder .
upma push-hf username/my-model --repo-type model --folder downloads\model-name
```

Private repo:

```cmd
upma push-hf username/my-private-dataset --repo-type dataset --folder . --private
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

## Stop

```cmd
upma stop
```
