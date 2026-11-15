@echo off
rem Automated backups: registers a Windows Scheduled Task that runs an encrypted
rem backup every night at 02:00 and keeps the last 14. Run once as Administrator.
rem Remove it later with:  schtasks /Delete /TN "EarthScape Nightly Backup" /F
set PROJECT=%~dp0..
schtasks /Create /TN "EarthScape Nightly Backup" /SC DAILY /ST 02:00 /F ^
  /TR "cmd /c cd /d \"%PROJECT%\" && python manage.py backup_earthscape --keep 14 >> logs\backup.log 2>&1"
echo.
echo Scheduled. Check it in Task Scheduler, or run now with:
echo   schtasks /Run /TN "EarthScape Nightly Backup"
