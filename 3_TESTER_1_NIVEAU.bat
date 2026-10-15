@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set PY=python
where py >NUL 2>NUL && set PY=py
%PY% automatisation_wow.py --niveaux 1 --debug
pause
