@echo off
REM Windows wrapper so `gamePredict <command>` works once this repo is on PATH.
python "%~dp0gamePredict.py" %*
