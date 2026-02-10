#!/bin/bash
set -e

echo "Starting installation for Ubuntu 24.04..."

# Update system
echo "Updating system packages..."
sudo apt update && sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y

# Install Python 3, pip, and venv (including python3-full/setuptools for distutils)
echo "Installing Python 3 and dependencies..."
# Removed libgconf-2-4 as it is not available in Ubuntu 24.04
sudo apt install -y python3 python3-pip python3-venv python3-full python3-setuptools wget curl unzip libxi6

# Install Node.js (LTS version 20.x)
echo "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify Node.js installation
echo "Node.js version: $(node -v)"
echo "npm version: $(npm -v)"

# Install Google Chrome Stable
echo "Downloading and installing Google Chrome Stable..."
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb

# Create Python Virtual Environment
echo "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# Install Python dependencies explicitly using the venv pip
echo "Installing Python dependencies..."
./venv/bin/pip install --upgrade pip
# Explicitly install setuptools first to fix "No module named 'distutils'" errors
./venv/bin/pip install setuptools
./venv/bin/pip install -r requirements.txt

# Install Node.js dependencies
echo "Installing Node.js dependencies..."
cd x-screenshot-araci
npm install
cd ..

# Make start script executable
chmod +x start.sh

# VERIFICATION STEP
echo "Verifying Selenium installation..."
if ./venv/bin/python3 -c "import selenium; import undetected_chromedriver; print('Selenium libraries imported successfully.')"; then
    echo "✔ Selenium and dependencies are correctly installed."
else
    echo "❌ ERROR: Selenium libraries could not be imported!"
    echo "Checking installed packages..."
    ./venv/bin/pip list
    echo "Please check the output above for errors."
    exit 1
fi

# FIREWALL SETTINGS (Merged from open_firewall.sh)
echo "Configuring Firewall (UFW) for port 5000..."
sudo ufw allow 5000/tcp
sudo ufw reload

echo "Installation complete!"
echo "Your Local IP Address: $(hostname -I | awk '{print $1}')"
echo "You can access the application from other devices via: http://$(hostname -I | awk '{print $1}'):5000"
echo "You can now run the application using: ./start.sh"
