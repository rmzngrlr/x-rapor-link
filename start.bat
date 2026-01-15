@echo off
echo Installing Python Dependencies...
pip install -r requirements.txt

echo Starting Node.js Server...
cd x-screenshot-araci
rem Check if node_modules exists, if not install
if not exist node_modules (
    echo Installing Node.js Dependencies...
    call npm install
)
rem Start Node.js server in a new window/background
start "X Screenshot Server" /min node server.js
cd ..

echo Starting Python Server...
start http://localhost:5000
python app.py

echo Stopping servers...
taskkill /F /IM node.exe
pause
