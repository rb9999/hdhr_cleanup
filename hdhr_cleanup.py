#!/usr/bin/env python3
"""
HDHomeRun DVR Auto Cleanup
Keeps only the newest N recordings per show.
Tested with SiliconDust HDHomeRun DVR API (recorded.json / recorded_delete).
"""

import requests
import time
import logging
import argparse
import sys
import json
import os
from dotenv import load_dotenv

# === DEFAULT CONFIG ===
# These defaults are used if config.json is not found
DEFAULT_DVR_IP = "192.168.86.34:59090"
DEFAULT_MAX_EPISODES = 5
DEFAULT_POLL_INTERVAL_MINUTES = 1

# === GLOBAL CONFIG ===
# Will be populated by load_config()
CONFIG = {}

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

def load_config(config_path="config.json"):
    """
    Load configuration from JSON file and environment variables.

    Priority order for dvr_ip:
    1. Environment variable DVR_IP (from .env)
    2. dvr_ip in config.json
    3. DEFAULT_DVR_IP constant

    Returns a dict with:
    - dvr_ip: DVR IP address
    - default_episodes: Default number of episodes to keep
    - poll_interval_minutes: Minutes between cleanup runs
    - show_overrides: Dict of show name -> episode count
    """
    # Load environment variables from .env file
    load_dotenv()

    if not os.path.exists(config_path):
        logging.warning(f"Config file {config_path} not found. Using defaults.")
        config = {
            "dvr_ip": DEFAULT_DVR_IP,
            "default_episodes": DEFAULT_MAX_EPISODES,
            "poll_interval_minutes": DEFAULT_POLL_INTERVAL_MINUTES,
            "show_overrides": {}
        }
    else:
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            # Validate and set defaults for missing keys
            config.setdefault("dvr_ip", DEFAULT_DVR_IP)
            config.setdefault("default_episodes", DEFAULT_MAX_EPISODES)
            config.setdefault("poll_interval_minutes", DEFAULT_POLL_INTERVAL_MINUTES)
            config.setdefault("show_overrides", {})

            logging.info(f"Loaded config from {config_path}")
            logging.debug(f"Config: {config}")

        except Exception as e:
            logging.error(f"Failed to load config file {config_path}: {e}")
            logging.warning("Using default configuration")
            config = {
                "dvr_ip": DEFAULT_DVR_IP,
                "default_episodes": DEFAULT_MAX_EPISODES,
                "poll_interval_minutes": DEFAULT_POLL_INTERVAL_MINUTES,
                "show_overrides": {}
            }

    # Override dvr_ip with environment variable if present
    env_dvr_ip = os.getenv("DVR_IP")
    if env_dvr_ip:
        config["dvr_ip"] = env_dvr_ip
        logging.info(f"Using DVR_IP from environment: {env_dvr_ip}")

    return config


def get_recordings():
    """Return list of all episodes across all series from the DVR."""
    dvr_ip = CONFIG.get("dvr_ip", DEFAULT_DVR_IP)
    try:
        url = f"http://{dvr_ip}/recorded_files.json"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()

        series_list = resp.json()
        all_episodes = []

        for series in series_list:
            series_id = series.get("SeriesID")
            series_title = series.get("Title")
            episodes_url = series.get("EpisodesURL")
            if not episodes_url:
                continue

            try:
                ep_resp = requests.get(episodes_url, timeout=5)
                ep_resp.raise_for_status()
                episodes = ep_resp.json()

                # Attach the series title to each episode for easier grouping later
                for ep in episodes:
                    ep["SeriesTitle"] = series_title
                all_episodes.extend(episodes)

            except Exception as inner_e:
                logging.warning(f"Failed to load episodes for {series_title}: {inner_e}")

        logging.info(f"Found {len(all_episodes)} total episodes across {len(series_list)} series.")
        return all_episodes

    except Exception as e:
        logging.warning(f"Failed to get recordings: {e}")
        return []


def extract_recording_id(recording):
    """Extract the recording ID from the recording data."""
    # Try to get ID from CmdURL or PlayURL
    cmd_url = recording.get("CmdURL", "")
    if "id=" in cmd_url:
        return cmd_url.split("id=")[1].split("&")[0]

    play_url = recording.get("PlayURL", "")
    if "id=" in play_url:
        return play_url.split("id=")[1].split("&")[0]

    # Fallback to FileID if it exists
    return recording.get("FileID")


def delete_recording(recording, title, episode_title):
    """Delete a recording using the HDHomeRun DVR API."""
    dvr_ip = CONFIG.get("dvr_ip", DEFAULT_DVR_IP)
    try:
        file_id = extract_recording_id(recording)
        if not file_id:
            logging.warning(f"Could not extract recording ID for {title} - {episode_title}")
            return False

        # Use the correct HDHomeRun delete endpoint (POST method)
        url = f"http://{dvr_ip}/recorded/cmd?cmd=delete&id={file_id}"
        logging.debug(f"Deleting with URL: {url}")

        resp = requests.post(url, timeout=5)
        logging.debug(f"Response: status={resp.status_code}")

        if resp.status_code == 200:
            logging.info(f"🗑️  Deleted: {title} - {episode_title} (ID: {file_id})")
            return True
        else:
            logging.warning(f"Failed to delete {title} - {episode_title}: HTTP {resp.status_code}")
            return False
    except Exception as e:
        logging.warning(f"Failed to delete recording: {e}")
        return False

def get_max_episodes_for_show(title, override_max=None):
    """
    Get the maximum episodes to keep for a show.

    Priority order:
    1. override_max (from command-line)
    2. show_overrides from config
    3. default_episodes from config
    """
    if override_max is not None:
        return override_max

    # Check if there's a config override for this show
    show_overrides = CONFIG.get("show_overrides", {})
    if title in show_overrides:
        return show_overrides[title]

    # Use default from config
    return CONFIG.get("default_episodes", DEFAULT_MAX_EPISODES)


def cleanup_all_shows(target_show=None, max_episodes=None):
    """
    Limit recordings for each show to max_episodes.

    Args:
        target_show: If provided, only clean up this specific show (case-insensitive)
        max_episodes: Number of episodes to keep (overrides config for all shows)
    """
    all_recordings = get_recordings()
    if not all_recordings:
        logging.info("No recordings found.")
        return

    # Group by Title
    shows = {}
    for r in all_recordings:
        title = r.get("Title", "Unknown")
        shows.setdefault(title, []).append(r)

    # If targeting a specific show, filter to just that one
    if target_show:
        # Case-insensitive search
        target_lower = target_show.lower()
        matching_shows = {title: recs for title, recs in shows.items()
                         if target_lower in title.lower()}

        if not matching_shows:
            logging.error(f"No show found matching '{target_show}'")
            logging.info(f"Available shows: {', '.join(sorted(shows.keys()))}")
            return

        if len(matching_shows) > 1:
            logging.info(f"Multiple shows match '{target_show}':")
            for title in sorted(matching_shows.keys()):
                logging.info(f"  - {title}")

        shows = matching_shows

    # Process each show
    for title, recs in shows.items():
        # Get max episodes for this specific show
        show_max = get_max_episodes_for_show(title, max_episodes)

        if len(recs) > show_max:
            # Sort by StartTime (oldest first)
            recs.sort(key=lambda x: x.get("StartTime", 0))

            # Handle the special case where show_max is 0 (delete all)
            if show_max == 0:
                to_delete = recs
            else:
                to_delete = recs[:-show_max]

            logging.info(f"{title}: {len(recs)} recordings → trimming to {show_max}")
            logging.debug(f"Recordings to delete: {[extract_recording_id(r) for r in to_delete]}")

            success_count = 0
            for r in to_delete:
                if delete_recording(r, title, r.get("EpisodeTitle", "")):
                    success_count += 1

            logging.info(f"Successfully deleted {success_count} of {len(to_delete)} recordings")
        else:
            logging.debug(f"{title}: {len(recs)} recordings (no cleanup needed, keeping {show_max})")

def main():
    parser = argparse.ArgumentParser(
        description="HDHomeRun DVR Auto Cleanup - Keep only the newest N recordings per show"
    )
    parser.add_argument(
        "-show", "--show",
        help="Target a specific show (case-insensitive partial match)"
    )
    parser.add_argument(
        "-max", "--max-episodes",
        type=int,
        help="Number of episodes to keep (overrides config for all shows)"
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config file (default: config.json)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all shows and their recording counts, then exit"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run cleanup once for all shows according to config, then exit"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously in monitoring mode (default if no --show or --once specified)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging to see API responses"
    )

    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    global CONFIG
    CONFIG = load_config(args.config)

    # List mode
    if args.list:
        all_recordings = get_recordings()
        if not all_recordings:
            logging.info("No recordings found.")
            return

        shows = {}
        for r in all_recordings:
            title = r.get("Title", "Unknown")
            shows.setdefault(title, []).append(r)

        logging.info(f"Found {len(shows)} shows:")
        for title in sorted(shows.keys()):
            logging.info(f"  {title}: {len(shows[title])} recordings")
        return

    # Single-run mode (when --show is specified)
    if args.show:
        logging.info(f"Running single cleanup for show matching '{args.show}'")
        cleanup_all_shows(target_show=args.show, max_episodes=args.max_episodes)
        logging.info("Cleanup complete.")
        return

    # One-time run mode (when --once is specified)
    if args.once:
        default_max = CONFIG.get("default_episodes", DEFAULT_MAX_EPISODES)

        if args.max_episodes:
            logging.info(f"Running one-time cleanup (keeping {args.max_episodes} per show, overriding config)")
        else:
            logging.info(f"Running one-time cleanup (default: {default_max} per show)")
            if CONFIG.get("show_overrides"):
                logging.info(f"Show overrides: {CONFIG['show_overrides']}")

        cleanup_all_shows(max_episodes=args.max_episodes)
        logging.info("Cleanup complete.")
        return

    # Continuous monitoring mode
    default_max = CONFIG.get("default_episodes", DEFAULT_MAX_EPISODES)
    poll_interval_minutes = CONFIG.get("poll_interval_minutes", DEFAULT_POLL_INTERVAL_MINUTES)
    poll_interval_seconds = poll_interval_minutes * 60

    if args.max_episodes:
        logging.info(f"Starting HDHomeRun cleanup script (keeping {args.max_episodes} per show, overriding config)")
    else:
        logging.info(f"Starting HDHomeRun cleanup script (default: {default_max} per show)")
        if CONFIG.get("show_overrides"):
            logging.info(f"Show overrides configured: {list(CONFIG['show_overrides'].keys())}")

    logging.info(f"Polling every {poll_interval_minutes} minute(s)")

    while True:
        cleanup_all_shows(max_episodes=args.max_episodes)
        time.sleep(poll_interval_seconds)

if __name__ == "__main__":
    main()
