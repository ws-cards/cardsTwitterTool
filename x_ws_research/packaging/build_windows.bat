@echo off
REM Build Windows onedir package. Run from repo's x_ws_research directory OR this folder.
setlocal
cd /d "%~dp0\.."

python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

REM Do NOT copy browser_profile / db / images into dist
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

python -m PyInstaller packaging\x_ws_research.spec --noconfirm
if errorlevel 1 exit /b 1

echo.
echo Build complete: dist\x_ws_research\
echo Next: install Playwright Chromium for the SAME Python/user that will run the app:
echo   set PLAYWRIGHT_BROWSERS_PATH=%%LOCALAPPDATA%%\x_ws_research\ms-playwright
echo   python -m playwright install chromium
echo See packaging\WINDOWS_CHECKLIST.md
endlocal
