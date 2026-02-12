@echo off
echo Starting Block All Tool on Port 3003...

cd x_blocker
if exist ..\venv (
    ..\venv\Scripts\python.exe app.py
) else (
    python app.py
)
pause
