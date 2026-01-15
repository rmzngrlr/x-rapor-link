#!/bin/bash

# Start Node.js server
echo "Starting Node.js server..."
cd x-screenshot-araci
node server.js &
NODE_PID=$!
cd ..

# Start Python Flask server
echo "Starting Python Flask server..."
python3 app.py &
PYTHON_PID=$!

# Trap SIGINT and SIGTERM to kill both processes
trap "kill $NODE_PID $PYTHON_PID; exit" SIGINT SIGTERM

# Wait for both processes
wait $NODE_PID $PYTHON_PID
