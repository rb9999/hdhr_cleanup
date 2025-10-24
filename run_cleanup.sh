#!/bin/bash
# Wrapper script for running hdhr_cleanup.py from Task Scheduler
# This ensures the working directory is correct so .env files are loaded properly

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script directory
cd "$SCRIPT_DIR"

# Check if venv exists, if not create it
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv "$SCRIPT_DIR/.venv"

    # Activate and install dependencies
    source "$SCRIPT_DIR/.venv/bin/activate"
    pip install requests python-dotenv
    deactivate

    echo "Virtual environment created and dependencies installed."
fi

# Run the cleanup script using the venv Python
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/hdhr_cleanup.py" "$@"
