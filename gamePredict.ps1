#!/usr/bin/env pwsh
# PowerShell wrapper so `gamePredict <command>` works once this repo is on PATH.
python "$PSScriptRoot/gamePredict.py" $args
exit $LASTEXITCODE
