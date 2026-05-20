# GitHub Publish Commands

Use these commands from PowerShell or Command Prompt after creating an empty GitHub repository.

Replace:

```text
https://github.com/YOUR_USERNAME/YOUR_REPO.git
```

with your real GitHub repository URL.

## First-Time Publish

```powershell
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
git init
git add .
git commit -m "Initial SO-101 upma robot project"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## Future Updates

```powershell
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
git add .
git commit -m "Update robot workflow"
git push
```

## Clone On A New Windows System

```powershell
cd C:\Users\PBL
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git so101_kitchen_stirrer_milestone
cd C:\Users\PBL\so101_kitchen_stirrer_milestone
powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
```

Then edit `config.json`, set the robot COM port, and follow:

```powershell
notepad config.json
notepad UPMA_CALIBRATION_GUIDE.md
```

## Files Intentionally Not Uploaded

The `.gitignore` blocks local/private files:

- `.venv/`
- `config.json`
- `.env`
- Python cache files
- dashboard logs
- camera snapshots

Do not upload OpenAI API keys.
