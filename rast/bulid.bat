@echo off
REM ----------------------------------------
REM Uruchomienie skryptu PowerShell
REM ----------------------------------------

REM Ścieżka do skryptu PS1
SET PS_SCRIPT=build_all.ps1

REM Uruchom PowerShell i wykonaj skrypt
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"

pause
