@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "TARGET=%USERPROFILE%\OneDrive\Desktop\gnani"
set "SRC=%~dp0"
set "BACKUP=%TARGET%\backup_before_stage10"
if not exist "%TARGET%\app\main.py" (
 echo ERROR: Existing gnani project not found at %TARGET%
 pause
 exit /b 1
)
if not exist "%SRC%app\deploy_guard.py" (
 echo ERROR: Extract the Stage 10 ZIP before starting update.bat
 pause
 exit /b 1
)
if /I "%SRC%"=="%TARGET%\" (
 echo ERROR: Run the installer from the extracted ZIP, outside gnani
 pause
 exit /b 1
)
if exist "%BACKUP%" (
 echo ERROR: Backup already exists: %BACKUP%. Rename it before retry.
 pause
 exit /b 1
)
echo.
echo Stage 10: test isolation, public demo guard, deployment and demo documentation.
echo Existing SQLite cases, local API key and .env will not be modified.
echo Stop Uvicorn before proceeding. Target: %TARGET%
choice /C YN /M "Stopped the existing Uvicorn server"
if errorlevel 2 exit /b 1
mkdir "%BACKUP%" || goto FAIL_BACKUP
if not exist "%TARGET%\app\static\index.html" goto FAIL
if not exist "%TARGET%\tests\test_api.py" goto FAIL
copy /Y "%TARGET%\app\main.py" "%BACKUP%\main.py" >nul || goto FAIL
copy /Y "%TARGET%\tests\test_api.py" "%BACKUP%\test_api.py" >nul || goto FAIL
if exist "%TARGET%\app\deploy_guard.py" copy /Y "%TARGET%\app\deploy_guard.py" "%BACKUP%\deploy_guard.py" >nul
if exist "%TARGET%\tests\test_stage10_public.py" copy /Y "%TARGET%\tests\test_stage10_public.py" "%BACKUP%\test_stage10_public.py" >nul
if exist "%TARGET%\README.md" copy /Y "%TARGET%\README.md" "%BACKUP%\README.md" >nul
if exist "%TARGET%\STAGE_STATUS.md" copy /Y "%TARGET%\STAGE_STATUS.md" "%BACKUP%\STAGE_STATUS.md" >nul
if exist "%TARGET%\.gitignore" copy /Y "%TARGET%\.gitignore" "%BACKUP%\gitignore.txt" >nul
if exist "%TARGET%\.env.example" copy /Y "%TARGET%\.env.example" "%BACKUP%\env_example.txt" >nul
if exist "%TARGET%\render.yaml" copy /Y "%TARGET%\render.yaml" "%BACKUP%\render.yaml" >nul
copy /Y "%SRC%app\main.py" "%TARGET%\app\main.py" >nul || goto FAIL
copy /Y "%SRC%app\deploy_guard.py" "%TARGET%\app\deploy_guard.py" >nul || goto FAIL
copy /Y "%SRC%tests\test_api.py" "%TARGET%\tests\test_api.py" >nul || goto FAIL
copy /Y "%SRC%tests\test_stage10_public.py" "%TARGET%\tests\test_stage10_public.py" >nul || goto FAIL
copy /Y "%SRC%README.md" "%TARGET%\README.md" >nul || goto FAIL
copy /Y "%SRC%STAGE_STATUS.md" "%TARGET%\STAGE_STATUS.md" >nul || goto FAIL
copy /Y "%SRC%render.yaml" "%TARGET%\render.yaml" >nul || goto FAIL
copy /Y "%SRC%.gitignore" "%TARGET%\.gitignore" >nul || goto FAIL
copy /Y "%SRC%.env.example" "%TARGET%\.env.example" >nul || goto FAIL
if not exist "%TARGET%\docs" mkdir "%TARGET%\docs" || goto FAIL
copy /Y "%SRC%docs\STAGE10_DEPLOYMENT.md" "%TARGET%\docs\STAGE10_DEPLOYMENT.md" >nul || goto FAIL
copy /Y "%SRC%docs\STAGE10_DEMO_SCRIPT.md" "%TARGET%\docs\STAGE10_DEMO_SCRIPT.md" >nul || goto FAIL
copy /Y "%SRC%docs\STAGE10_RELEASE_CHECKLIST.md" "%TARGET%\docs\STAGE10_RELEASE_CHECKLIST.md" >nul || goto FAIL
cd /d "%TARGET%"
echo.
echo Running offline regression tests. Live API mode is temporarily masked for this command only.
set "GNANI_MODE=mock"
py -m unittest discover -s tests -v
if errorlevel 1 goto FAIL
echo.
echo Running synthetic parser benchmark...
py benchmarks\run_benchmark.py
if errorlevel 1 goto FAIL
echo.
echo SUCCESS: Stage 10 installed. Current CMD / system API key was not changed.
echo Review docs\STAGE10_DEPLOYMENT.md and docs\STAGE10_DEMO_SCRIPT.md
pause
exit /b 0
:FAIL
echo.
echo ERROR: Update or tests failed. Restoring prior application files.
if exist "%BACKUP%\main.py" copy /Y "%BACKUP%\main.py" "%TARGET%\app\main.py" >nul
if exist "%BACKUP%\test_api.py" copy /Y "%BACKUP%\test_api.py" "%TARGET%\tests\test_api.py" >nul
if exist "%BACKUP%\deploy_guard.py" (copy /Y "%BACKUP%\deploy_guard.py" "%TARGET%\app\deploy_guard.py" >nul) else (if exist "%TARGET%\app\deploy_guard.py" del /q "%TARGET%\app\deploy_guard.py")
if exist "%BACKUP%\test_stage10_public.py" (copy /Y "%BACKUP%\test_stage10_public.py" "%TARGET%\tests\test_stage10_public.py" >nul) else (if exist "%TARGET%\tests\test_stage10_public.py" del /q "%TARGET%\tests\test_stage10_public.py")
if exist "%BACKUP%\README.md" copy /Y "%BACKUP%\README.md" "%TARGET%\README.md" >nul
if exist "%BACKUP%\STAGE_STATUS.md" copy /Y "%BACKUP%\STAGE_STATUS.md" "%TARGET%\STAGE_STATUS.md" >nul
if exist "%BACKUP%\gitignore.txt" copy /Y "%BACKUP%\gitignore.txt" "%TARGET%\.gitignore" >nul
if exist "%BACKUP%\env_example.txt" copy /Y "%BACKUP%\env_example.txt" "%TARGET%\.env.example" >nul
if exist "%BACKUP%\render.yaml" (copy /Y "%BACKUP%\render.yaml" "%TARGET%\render.yaml" >nul) else (if exist "%TARGET%\render.yaml" del /q "%TARGET%\render.yaml")
echo Application files restored. Some documentation files may remain.
echo Backup: %BACKUP%
pause
exit /b 1
:FAIL_BACKUP
echo ERROR: Could not create backup. No app files modified.
pause
exit /b 1
