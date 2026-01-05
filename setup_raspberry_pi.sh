#!/bin/bash
# HealthDiary Raspberry Pi Setup Script
# This script automates the setup process for HealthDiary on Raspberry Pi

set -e  # Exit on error

echo "========================================="
echo "HealthDiary Raspberry Pi Setup Script"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    print_error "Please do not run this script as root. Run as your regular user."
    exit 1
fi

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

print_status "Working directory: $SCRIPT_DIR"

# Step 1: Update system packages
print_status "Step 1: Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Step 2: Install system dependencies
print_status "Step 2: Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    build-essential \
    portaudio19-dev \
    python3-dev \
    alsa-utils \
    pulseaudio \
    pulseaudio-utils \
    sox \
    libasound2-dev \
    ffmpeg

# Step 3: Check Python version
PYTHON_VERSION=$(python3 --version)
print_status "Python version: $PYTHON_VERSION"

# Step 4: Create virtual environment
print_status "Step 4: Creating Python virtual environment..."
if [ -d ".venv" ]; then
    print_warning "Virtual environment already exists. Removing old one..."
    rm -rf .venv
fi
python3 -m venv .venv

# Step 5: Activate virtual environment and upgrade pip
print_status "Step 5: Setting up Python environment..."
source .venv/bin/activate
pip install --upgrade pip setuptools wheel

# Step 6: Install Python dependencies
print_status "Step 6: Installing Python dependencies..."
if [ ! -f "backend/requirements.txt" ]; then
    print_error "backend/requirements.txt not found!"
    exit 1
fi
pip install -r backend/requirements.txt

# Step 7: Create data directory
print_status "Step 7: Creating data directories..."
mkdir -p backend/app/data
mkdir -p temp_audio

# Step 8: Test audio devices
print_status "Step 8: Checking audio devices..."
echo ""
echo "=== Input Devices (Microphones) ==="
arecord -l || print_warning "No recording devices found or arecord not available"
echo ""
echo "=== Output Devices (Speakers) ==="
aplay -l || print_warning "No playback devices found or aplay not available"
echo ""

# Step 9: Check for .env file
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Creating template..."
    cat > .env << EOF
# Qwen LLM Configuration (Required for transcription and NLU features)
QWEN_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions
QWEN_API_KEY=your_api_key_here
QWEN_MODEL=qwen2.5-7b-instruct
QWEN_SPEECH_MODEL=qwen2.5-omni-7b
EOF
    print_warning "Please edit .env file and add your QWEN_API_KEY!"
else
    print_status ".env file already exists"
fi

# Step 10: Create startup script
print_status "Step 10: Creating startup script..."
cat > start_healthdiary.sh << 'STARTEOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate

# Load .env file if it exists (requires python-dotenv)
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start the server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
STARTEOF

chmod +x start_healthdiary.sh

# Step 11: Verify installation
print_status "Step 11: Verifying installation..."
python3 -c "import fastapi, uvicorn, sqlalchemy; print('✓ All packages installed successfully!')" || {
    print_error "Package verification failed!"
    exit 1
}

# Step 12: Get IP address
IP_ADDRESS=$(hostname -I | awk '{print $1}')
print_status "Raspberry Pi IP Address: $IP_ADDRESS"

# Summary
echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
print_status "Next steps:"
echo "  1. Edit .env file and add your QWEN_API_KEY:"
echo "     nano .env"
echo ""
echo "  2. Test audio devices:"
echo "     arecord -f cd -t wav test.wav    # Record test audio"
echo "     aplay test.wav                    # Play test audio"
echo ""
echo "  3. Start the server:"
echo "     ./start_healthdiary.sh"
echo "     OR"
echo "     source .venv/bin/activate"
echo "     uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "  4. Test the API:"
echo "     curl http://localhost:8000/healthz"
echo "     curl http://$IP_ADDRESS:8000/healthz  (from another device)"
echo ""
echo "  5. (Optional) Set up as a system service - see RASPBERRY_PI_SETUP.md"
echo ""
print_warning "Remember to configure your QWEN_API_KEY in the .env file!"
echo ""

