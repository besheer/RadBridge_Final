@echo off
setlocal EnableDelayedExpansion
title RadBridge Word Companion Setup

echo ========================================================
echo        RadBridge Word Companion Installer
echo ========================================================
echo.

taskkill /F /FI "WINDOWTITLE eq RadBridge*" >nul 2>&1

set "TARGET_DIR=%LOCALAPPDATA%\RadBridge"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

echo [1/3] Copying files to: %TARGET_DIR% ...
copy /Y "%~dp0RadBridgeWordCompanion.ps1" "%TARGET_DIR%\" >nul
if exist "%~dp0radbridge_word_companion.pyw" copy /Y "%~dp0radbridge_word_companion.pyw" "%TARGET_DIR%\" >nul

echo [2/3] Registering URL Protocol in Windows Registry...
reg add "HKCU\Software\Classes\radbridge-word" /ve /d "URL:RadBridge Word Protocol" /f >nul
reg add "HKCU\Software\Classes\radbridge-word" /v "URL Protocol" /d "" /f >nul
reg add "HKCU\Software\Classes\radbridge-word\shell\open\command" /ve /d "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%TARGET_DIR%\RadBridgeWordCompanion.ps1\" \"%%1\"" /f >nul

echo [3/3] Verifying registration...
reg query "HKCU\Software\Classes\radbridge-word\shell\open\command" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Registry setup failed.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   SUCCESS: RadBridge Word Companion is now installed!
echo ========================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[System.Windows.Forms.MessageBox]::Show('تم تثبيت وتحديث أداة RadBridge Word Companion بنجاح تام!`n`nيمكنك الآن الضغط على زر Word المباشر في المتصفح وسيتم فتح التقرير وحفظه بسلاسة.', 'RadBridge Word Companion', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information)"

pause
