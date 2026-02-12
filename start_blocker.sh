#!/bin/bash

# Start Block All Python Flask server (Port 3003)
echo "Starting Block All Tool on Port 3003..."

# Change to the x_blocker directory so it can find its templates/static easily relative to itself
cd x_blocker

if [ -d "../venv" ]; then
    ../venv/bin/python3 app.py
else
    python3 app.py
fi
