@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set PY=python
where py >NUL 2>NUL && set PY=py
%PY% automatisation_wow.py --verifier
echo.
echo Ouvre capture_test_annote.png pour voir ce que le bot a detecte.
pause
