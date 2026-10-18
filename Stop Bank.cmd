@echo off
title Stop Global Bank Tester
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1" -Action Stop
if errorlevel 1 pause
