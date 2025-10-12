# HDHomeRun DVR Auto Cleanup

Automatically manage your HDHomeRun DVR recordings by keeping only the newest N episodes per show. Perfect for keeping your DVR storage under control without manually deleting old recordings.

## Features

- **Per-Show Retention Policies**: Set different episode limits for each show
- **Automatic Cleanup**: Run continuously or on-demand
- **Flexible Configuration**: JSON config file with environment variable support
- **Multiple Execution Modes**: One-time, targeted, or continuous monitoring
- **Safe Deletion**: Only deletes oldest episodes, always keeps the newest
- **Detailed Logging**: Track what's being deleted and why

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/rb9999/hdhr_cleanup
cd hdhr_cleanup

# Install dependencies (system-wide)
pip install -r requirements.txt
```

**Note**: This installs `requests` and `python-dotenv` to your system Python. If you prefer to isolate dependencies, see the optional virtual environment setup below.

<details>
<summary><b>Optional: Use a Virtual Environment (Recommended for Development)</b></summary>

A virtual environment isolates dependencies from your system Python. This is recommended for developers but not required for end users:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (Git Bash)
source .venv/Scripts/activate
# Windows (PowerShell)
.venv\Scripts\activate.ps1
# Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

</details>

### 2. Configuration

**Create config files from templates:**

```bash
cp .env.example .env
cp config.json.example config.json
```

**Edit `.env`** and set your DVR IP:
```
DVR_IP=192.168.1.100:59090
```

**Edit `config.json`** to set your retention policies:
```json
{
  "default_episodes": 5,
  "poll_interval_minutes": 60,
  "show_overrides": {
    "Gilligans Island": 1,
    "Star Trek": 3,
    "Jeopardy!": 7,
    "The Price is Right": 4
  }
}
```

**Note**:
- `DVR_IP` comes from `.env` (keeps your IP private)
- `config.json` contains your show retention policies
- Both files are in `.gitignore` and won't be committed

### 3. Run

```bash
# One-time cleanup using config.json settings
python hdhr_cleanup.py --once

# Continuous monitoring (runs forever)
python hdhr_cleanup.py

# List all shows and their recording counts
python hdhr_cleanup.py --list
```

## Usage Modes

### 1. One-Time Cleanup (All Shows)

Run cleanup once according to your config, then exit:

```bash
# Use config.json settings
python hdhr_cleanup.py --once

# Override all shows to keep 10 episodes
python hdhr_cleanup.py --once -max 10
```

**Perfect for:**
- Scheduled tasks (cron, Windows Task Scheduler)
- Manual cleanups
- Testing your configuration

### 2. Single Show Cleanup

Target a specific show for one-time cleanup:

```bash
# Keep only 2 episodes of "The Price is Right"
python hdhr_cleanup.py -show "The Price is Right" -max 2

# Partial matching works (case-insensitive)
python hdhr_cleanup.py -show "price" -max 2
```

### 3. List Shows

See all your recorded shows and counts:

```bash
python hdhr_cleanup.py --list
```

Output:
```
Found 5 shows:
  Jeopardy!: 10 recordings
  NBC Nightly News With Tom Llamas: 2 recordings
  New York Homicide: 1 recordings
  The Price is Right: 5 recordings
  Wheel of Fortune: 8 recordings
```

### 4. Continuous Monitoring

Run in the background and automatically clean up at intervals:

```bash
# Use config.json settings (polls every poll_interval_minutes)
python hdhr_cleanup.py

# Override to keep 10 episodes of all shows
python hdhr_cleanup.py -max 10
```

This mode runs forever until stopped (Ctrl+C).

## Configuration

### config.json

```json
{
  "dvr_ip": "192.168.1.100:59090",
  "default_episodes": 5,
  "poll_interval_minutes": 60,
  "show_overrides": {
    "Show Name": episodes_to_keep
  }
}
```

**Options:**
- `dvr_ip`: Your HDHomeRun DVR IP and port (optional if using `.env`)
- `default_episodes`: Default number of episodes to keep for all shows
- `poll_interval_minutes`: How often to check for cleanup in continuous mode
- `show_overrides`: Per-show episode limits (must match exact show name)

**Special Values:**
- Set a show to `0` to delete ALL recordings of that show
- Shows not in `show_overrides` use `default_episodes`

### Environment Variables (.env)

Store sensitive information like your DVR IP in `.env`:

```
DVR_IP=192.168.1.100:59090
```

**Priority order:**
1. `DVR_IP` environment variable (`.env` file)
2. `dvr_ip` in `config.json`
3. Built-in default

### Show Name Matching

For `show_overrides` in config.json, you **must use the exact show name** as it appears on your DVR.

Use `--list` to see exact names:
```bash
python hdhr_cleanup.py --list
```

## Command-Line Arguments

```
python hdhr_cleanup.py [OPTIONS]

Options:
  -show SHOW, --show SHOW
                        Target a specific show (case-insensitive partial match), then exit
  -max N, --max-episodes N
                        Number of episodes to keep (overrides config for all shows)
  --config PATH         Path to config file (default: config.json)
  --list                List all shows and their recording counts, then exit
  --once                Run cleanup once for all shows according to config, then exit
  --continuous          Run continuously in monitoring mode (default when no flags specified)
  --debug               Enable debug logging to see detailed API requests and responses
  -h, --help            Show help message and exit
```

## Examples

### Example 1: Daily Scheduled Cleanup

**Linux/Mac (cron):**
```bash
# Run cleanup every day at 3 AM
0 3 * * * cd /path/to/hdhr_cleanup && python hdhr_cleanup.py --once

# Or if using virtual environment:
0 3 * * * cd /path/to/hdhr_cleanup && .venv/bin/python hdhr_cleanup.py --once
```

**Windows (Task Scheduler):**
- Action: Start a program
- Program: `python` (or `C:\path\to\hdhr_cleanup\.venv\Scripts\python.exe` if using venv)
- Arguments: `hdhr_cleanup.py --once`
- Start in: `C:\path\to\hdhr_cleanup`

### Example 2: Different Retention by Show Type

```json
{
  "default_episodes": 5,
  "show_overrides": {
    "Daily News Show": 1,
    "Weekly Drama": 4,
    "Limited Series": 0,
    "Favorite Show": 20
  }
}
```

### Example 3: Clean Up Before Running Out of Space

```bash
# Emergency cleanup - keep only 1 episode of everything
python hdhr_cleanup.py --once -max 1
```

## How It Works

1. Connects to your HDHomeRun DVR via HTTP API
2. Fetches list of all recorded shows and episodes
3. For each show:
   - Determines retention limit (config override → default → 5)
   - Sorts recordings by date (oldest first)
   - Deletes oldest recordings until only N newest remain
4. Logs all actions with timestamps

**Safety Features:**
- Only deletes when recording count exceeds limit
- Always keeps the newest episodes
- Never deletes the only recording unless explicitly set to 0
- Reports success/failure for each deletion

## Troubleshooting

### "No recordings found"

- Check your `DVR_IP` is correct
- Ensure HDHomeRun DVR is powered on and accessible
- Try accessing `http://YOUR_DVR_IP/recorded_files.json` in browser

### "No show found matching 'X'"

- Use `--list` to see exact show names
- Show names in `show_overrides` must be exact matches
- Use `-show` with partial matching for command-line targeting

### Deletions Not Working

- Run with `--debug` to see detailed API responses
- Check if recordings are actually on the DVR
- Verify you have network access to the DVR

### Debug Mode

Run with `--debug` for detailed logging:
```bash
python hdhr_cleanup.py --once --debug
```

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

MIT License - feel free to use and modify as needed.

## Credits

Works with [SiliconDust HDHomeRun DVR](https://www.silicondust.com/) devices and their HTTP API.

## Disclaimer

This tool deletes recordings permanently. Test with `--list` and small retention numbers first. Always maintain backups of important recordings.
