@echo off
cd /d "%~dp0"
py emergency_blood_bank.py
if errorlevel 1 pause
