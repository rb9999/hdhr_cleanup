# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python utility for automatically managing HDHomeRun DVR recordings. The script continuously monitors a HDHomeRun DVR via its HTTP API and automatically deletes older recordings to keep only the newest N episodes per show.

## Development Setup

### Virtual Environment

The project uses a Python virtual environment located in `.venv/`:

```bash
# Activate virtual environment (Windows/Git Bash)
source .venv/Scripts/activate

# Activate virtual environment (Windows/PowerShell)
.venv\Scripts\activate.ps1
```

### Dependencies

The project requires `requests` and `python-dotenv`. To install:

```bash
pip install requests python-dotenv
```

## Running the Script

### Configuration

The script uses two configuration sources:

**1. Environment Variables (.env file)**

Store sensitive information like your DVR IP in [.env](.env):
```
DVR_IP=192.168.1.100:59090
```

Copy [.env.example](.env.example) to create your `.env` file. This file is gitignored and won't be committed.

**2. Configuration File (config.json)**

[config.json](config.json) contains retention policies and other settings:

```json
{
  "dvr_ip": "192.168.1.100:59090",
  "default_episodes": 5,
  "poll_interval_minutes": 60,
  "show_overrides": {
    "Example Show 1": 3,
    "Example Show 2": 7
  }
}
```

**Configuration Options:**
- `dvr_ip`: IP address and port of your HDHomeRun DVR (optional if using `.env`)
- `default_episodes`: Default number of recordings to keep per show
- `poll_interval_minutes`: Minutes between cleanup runs in continuous mode
- `show_overrides`: Per-show episode retention (exact show name match required)

**DVR IP Priority Order:**
1. `DVR_IP` environment variable (from `.env` file)
2. `dvr_ip` in `config.json`
3. Built-in default

**Episode Retention Priority Order:**
1. Command-line `-max` argument (overrides everything for all shows)
2. Show-specific override in `show_overrides`
3. `default_episodes` value

**For Development:**

Both `.env` and `config.json` are gitignored, so you can use them for your actual settings without worrying about committing sensitive data. The repository includes `config.json.example` as a template for others.

### Command-Line Usage

The script supports multiple modes of operation:

**1. One-Time Cleanup (All Shows)**
```bash
# Run once using config.json settings, then exit
python hdhr_cleanup.py --once

# Run once with override for all shows
python hdhr_cleanup.py --once -max 10
```

**2. Single Show Cleanup (One-time)**
```bash
# Trim a specific show to N episodes
python hdhr_cleanup.py -show "The Price is Right" -max 2

# Partial matching works (case-insensitive)
python hdhr_cleanup.py -show "price" -max 2
```

**3. List All Shows**
```bash
# See all shows and their recording counts
python hdhr_cleanup.py --list
```

**4. Continuous Monitoring (Default)**
```bash
# Run continuously, checking all shows at poll_interval_minutes
python hdhr_cleanup.py

# Run continuously with custom max episodes (overrides config)
python hdhr_cleanup.py -max 10
```

### Command-Line Arguments

- `-show`, `--show`: Target a specific show (case-insensitive partial match), then exit
- `-max`, `--max-episodes`: Number of episodes to keep (overrides config for all shows)
- `--config`: Path to config file (default: config.json)
- `--list`: List all shows and their recording counts, then exit
- `--once`: Run cleanup once for all shows according to config, then exit
- `--continuous`: Run continuously in monitoring mode (default when no flags specified)
- `--debug`: Enable debug logging to see detailed API requests and responses

## Architecture

### Core Components

**Main Script: [hdhr_cleanup.py](hdhr_cleanup.py)**

The script is a single-file application with key functions:

1. **`load_config(config_path)`** ([hdhr_cleanup.py:33](hdhr_cleanup.py#L33))
   - Loads environment variables from `.env` file using `python-dotenv`
   - Loads configuration from JSON file
   - Overrides `dvr_ip` with `DVR_IP` environment variable if present
   - Returns dict with `dvr_ip`, `default_episodes`, `poll_interval_minutes`, and `show_overrides`
   - Falls back to built-in defaults if config file not found

2. **`get_recordings()`** ([hdhr_cleanup.py:76](hdhr_cleanup.py#L76))
   - Fetches all recordings from DVR using `/recorded_files.json` endpoint
   - Iterates through each series and fetches episodes via `EpisodesURL`
   - Returns flattened list of all episodes across all series
   - Uses `dvr_ip` from CONFIG

3. **`extract_recording_id(recording)`** ([hdhr_cleanup.py:120](hdhr_cleanup.py#L120))
   - Extracts the recording ID from `CmdURL` or `PlayURL` fields
   - Recording IDs are embedded in URLs like `http://.../recorded/cmd?id=fa959e2f15bf0938`
   - Falls back to `FileID` if present (though recordings typically don't have this field)

4. **`delete_recording(recording, title, episode_title)`** ([hdhr_cleanup.py:130](hdhr_cleanup.py#L130))
   - Deletes a recording using POST to `/recorded/cmd?cmd=delete&id={id}`
   - Extracts ID from recording object using `extract_recording_id()`
   - Returns True/False for success tracking

5. **`get_max_episodes_for_show(title, override_max)`** ([hdhr_cleanup.py:156](hdhr_cleanup.py#L156))
   - Determines max episodes for a specific show
   - Priority: command-line override → show_overrides config → default_episodes config
   - Enables per-show retention policies

6. **`cleanup_all_shows(target_show=None, max_episodes=None)`** ([hdhr_cleanup.py:177](hdhr_cleanup.py#L177))
   - Groups recordings by Title
   - If `target_show` is specified, filters to only matching shows (case-insensitive partial match)
   - For each show, gets max episodes using `get_max_episodes_for_show()`
   - Deletes oldest recordings to meet retention policy
   - Tracks and reports deletion success count

7. **`main()`** ([hdhr_cleanup.py:237](hdhr_cleanup.py#L237))
   - Parses command-line arguments using argparse
   - Loads configuration from JSON file
   - Supports four modes: list shows, single show cleanup, one-time cleanup (all shows), or continuous monitoring
   - In continuous mode, uses `poll_interval_minutes` from config

### HDHomeRun API Integration

The script uses the SiliconDust HDHomeRun DVR HTTP API:
- **Series List**: `GET http://{DVR_IP}/recorded_files.json` - Returns list of all series
- **Episodes**: `GET {EpisodesURL}` - URL provided in each series object (e.g., `/recorded_files.json?SeriesID=...`)
- **Delete**: `POST http://{DVR_IP}/recorded/cmd?cmd=delete&id={recording_id}` - Deletes a recording

**Important Notes:**
- Recording IDs are not directly available as fields; they must be extracted from `CmdURL` or `PlayURL` fields
- The delete endpoint requires POST method (GET returns 400 Bad Request)
- Each recording has `CmdURL` and `PlayURL` fields containing the recording ID

### Data Flow

1. Load configuration from `config.json`
2. Fetch all series from `/recorded_files.json`
3. For each series, fetch episodes from `EpisodesURL`
4. Group all episodes by show title
5. For each show:
   - Determine max episodes (check show_overrides, then default_episodes)
   - If recording count exceeds max, sort by StartTime (oldest first)
   - Delete oldest recordings to meet retention policy
6. In continuous mode, wait `poll_interval_minutes` and repeat

## Logging

The script uses Python's `logging` module with INFO level by default. All cleanup operations are logged with timestamps.
