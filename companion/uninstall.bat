@echo off
chcp 65001 >nul
title RadBridge Word Companion Uninstaller

echo ========================================================
echo     إلغاء تثبيت أداة RadBridge Word Companion
echo ========================================================
echo.
echo جاري حذف تسجيل بروتوكول radbridge-word من سجل الويندوز...
reg delete "HKCU\Software\Classes\radbridge-word" /f >nul 2>&1
echo تم إزالة التسجيل بنجاح.
echo.
pause
