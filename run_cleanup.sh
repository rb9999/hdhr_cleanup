#!/bin/bash
# Wrapper script for running hdhr_cleanup.py from Task Scheduler
# This ensures the working directory is correct so .env files are loaded properly

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script directory
cd "$SCRIPT_DIR"

# Run the cleanup script using the venv Python
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/hdhr_cleanup.py" "$@"
