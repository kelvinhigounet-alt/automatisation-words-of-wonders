@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set PY=python
where py >NUL 2>NUL && set PY=py
echo Bot Words of Wonders - Ctrl+C pour arreter
%PY% automatisation_wow.py %*
pause
