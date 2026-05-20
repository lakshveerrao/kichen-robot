# SO-101 Upma Calibration Guide

Use this guide to calibrate and run the full upma workflow:

1. Connect and calibrate the SO-101 follower.
2. Save the main stirring poses.
3. Save the ingredient cup poses.
4. Save the spoon/stirrer pickup poses.
5. Validate without movement.
6. Run slow real movement.
7. Run the full upma sequence.

Keep one hand near the robot power switch during every real movement command.

## 1. Open PowerShell

Run:

```powershell
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
```

## 2. Clear Python And Check The Robot Port

Try to stop any old Python robot process:

```powershell
taskkill /F /IM python.exe
```

If Windows says `Access denied`, continue and check the port anyway.

Check serial ports:

```powershell
mode
```

Also try:

```powershell
powershell -Command "Get-CimInstance Win32_SerialPort | Select DeviceID,Name"
```

If Windows says `Access denied`, use the `mode` output.

If you see `COM7`, test the robot:

```powershell
.\.venv\Scripts\python.exe connect_test.py
```

If no robot COM port appears, unplug and replug USB, try another USB cable or port, then run:

```powershell
.\.venv\Scripts\lerobot-find-port.exe
```

Do not calibrate until a robot COM port appears.

## 3. Run Real LeRobot Calibration

Run:

```powershell
.\.venv\Scripts\lerobot-calibrate.exe --robot.type=so101_follower --robot.port=COM7 --robot.id=kitchen_stirrer_follower
```

After calibration finishes, test connection again:

```powershell
.\.venv\Scripts\python.exe connect_test.py
```

## 4. Save Main Upma And Stirring Poses

Move the robot by hand or teleop to each pose first. Then run only the matching command.

Do not run this whole list at once. Each command saves the robot's current physical pose.

```powershell
.\.venv\Scripts\python.exe save_position.py HOME
.\.venv\Scripts\python.exe save_position.py ABOVE_BOWL
.\.venv\Scripts\python.exe save_position.py STIR_DEPTH
.\.venv\Scripts\python.exe save_position.py LIFT
.\.venv\Scripts\python.exe save_position.py PARK
.\.venv\Scripts\python.exe save_position.py STIR_FORWARD
.\.venv\Scripts\python.exe save_position.py STIR_BACK
.\.venv\Scripts\python.exe save_position.py STIR_LEFT
.\.venv\Scripts\python.exe save_position.py STIR_RIGHT
.\.venv\Scripts\python.exe save_position.py UP
.\.venv\Scripts\python.exe save_position.py DOWN
.\.venv\Scripts\python.exe save_position.py LEFT
.\.venv\Scripts\python.exe save_position.py RIGHT
```

Recommended meaning:

- `HOME`: safe starting pose.
- `ABOVE_BOWL`: above the pan or bowl.
- `STIR_DEPTH`: spoon/stirrer lightly touching food.
- `LIFT`: raised safe travel pose near the pan.
- `PARK`: safe final pose.
- `STIR_FORWARD`: front stir point.
- `STIR_BACK`: back stir point.
- `STIR_LEFT`: left stir point.
- `STIR_RIGHT`: right stir point.
- `UP`, `DOWN`, `LEFT`, `RIGHT`: simple manual test poses.

## 5. Save Ingredient Cup Poses

Move the robot to each cup pose first, then run the matching command.

```powershell
.\.venv\Scripts\python.exe save_position.py CUP_APPROACH
.\.venv\Scripts\python.exe save_position.py CUP_GRASP
.\.venv\Scripts\python.exe save_position.py CUP_LIFT
.\.venv\Scripts\python.exe save_position.py CUP_POUR
.\.venv\Scripts\python.exe save_position.py CUP_PLACE
.\.venv\Scripts\python.exe save_position.py CUP_RELEASE
```

Pose meaning:

- `CUP_APPROACH`: above or near the ingredient cup.
- `CUP_GRASP`: gripper around the cup.
- `CUP_LIFT`: cup lifted safely.
- `CUP_POUR`: cup positioned or tilted over the pan.
- `CUP_PLACE`: cup returned to the holder or table.
- `CUP_RELEASE`: gripper open after placing the cup.

## 6. Save Spoon Or Stirrer Pickup Poses

Move the robot to each spoon/stirrer pose first, then run the matching command.

```powershell
.\.venv\Scripts\python.exe save_position.py STIRRER_APPROACH
.\.venv\Scripts\python.exe save_position.py STIRRER_GRASP
.\.venv\Scripts\python.exe save_position.py STIRRER_LIFT
.\.venv\Scripts\python.exe save_position.py STIRRER_READY
```

Pose meaning:

- `STIRRER_APPROACH`: near the spoon or stirrer.
- `STIRRER_GRASP`: gripper holding the spoon or stirrer.
- `STIRRER_LIFT`: spoon or stirrer lifted safely.
- `STIRRER_READY`: spoon or stirrer over or near the pan, ready to stir.

## 7. Validate Without Movement

Check the basic upma path:

```powershell
.\.venv\Scripts\python.exe upma_mode.py --dry-run --yes
```

Check the ingredient and spoon/stirrer path:

```powershell
.\.venv\Scripts\python.exe ingredient_actions.py --action all --dry-run
.\.venv\Scripts\python.exe upma_mode.py --dry-run --with-ingredients --yes
```

## 8. Test Small Real Motions

Run these slowly:

```powershell
.\.venv\Scripts\python.exe stir_motion.py --motion front-back --cycles 1 --speed-scale 0.02
.\.venv\Scripts\python.exe stir_motion.py --motion left-right --cycles 1 --speed-scale 0.02
```

Test ingredient cup and spoon/stirrer pickup only:

```powershell
.\.venv\Scripts\python.exe ingredient_actions.py --action all --speed-scale 0.02 --pause 0.6
```

## 9. Run Full Upma Without Ingredient Pickup

Use this if a human is adding ingredients:

```powershell
.\.venv\Scripts\python.exe upma_mode.py --yes --speed-scale 0.02 --cycles-multiplier 1 --pause 0.15 --low-pressure-lift-deg 6
```

## 10. Run Full Upma With Ingredient Cup And Spoon Pickup

Use this for the full sequence:

```powershell
.\.venv\Scripts\python.exe upma_mode.py --with-ingredients --yes --speed-scale 0.02 --cycles-multiplier 1 --pause 0.15 --low-pressure-lift-deg 6
```

## 11. Optional Dashboard

Start the localhost dashboard:

```powershell
.\.venv\Scripts\python.exe kitchen_robot_server.py --allow-movement
```

Open:

```text
http://127.0.0.1:8000
```

Use the checkbox labeled `Pick cup and side stirrer first` to include ingredient and spoon/stirrer pickup.

## 12. Emergency Stop

Use the physical robot power switch first if motion is unsafe.

You can also stop Python processes:

```powershell
taskkill /F /IM python.exe
```

If that returns `Access denied`, close the PowerShell window running the robot command, or use the physical power switch.
