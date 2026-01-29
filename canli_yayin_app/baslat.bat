@echo off
cd /d "%~dp0"

if not exist "node_modules" (
    echo node_modules eksik. Kurulum yapiliyor...
    call npm install
)

npm run dev -- --open
