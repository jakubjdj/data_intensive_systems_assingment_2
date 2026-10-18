@echo off
title Global Bank Tester
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1" -Action Start
if errorlevel 1 pause
