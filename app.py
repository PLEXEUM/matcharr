"""
Matcharr - Compare Sonarr/Radarr data to Plex libraries and fix mismatches.
"""

import json
import time
import sys
import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from tqdm import tqdm
from datetime import datetime

from arr import fetch_all_instances
from plex import fetch_plex_libraries, update_plex_match, normalize_path, map_plex_paths

# Create logs directory if it doesn't exist
LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging to both file and console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        TimedRotatingFileHandler(
            os.path.join(LOG_DIR, "matcharr.log"),
            when="midnight",  # Rotate daily at midnight
            backupCount=5      # Keep 5 days
        ),
        logging.StreamHandler()
    ]
)

# Get logger instance FIRST (before using it)
logger = logging.getLogger(__name__)

# Get cron schedule from environment variable
CRON_SCHEDULE = os.environ.get('CRON_SCHEDULE', '0 2 * * *')
logger.info(f"Scheduled to run at: {CRON_SCHEDULE}")


def timeoutput():
    """Return formatted timestamp for logging."""
    return datetime.now().strftime('%d %b %Y %H:%M:%S')


def main():
    start_time = time.time()
    
    logger.info(f"{timeoutput()} - Starting Matcharr")
    
    # Load configuration
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error(f"{timeoutput()} - ERROR: config.json not found")
        return
    except json.JSONDecodeError as e:
        logger.error(f"{timeoutput()} - ERROR: Invalid config.json: {e}")
        return
    
    # Validate config
    if not config.get("plex_url") or not config.get("plex_token"):
        logger.error(f"{timeoutput()} - ERROR: Plex URL and token are required")
        return
    
    # Get root folders from config (like Gaparr)
    sonarr_root = config.get("sonarr_root_folder", "")
    radarr_root = config.get("radarr_root_folder", "")
    
    if not sonarr_root and not radarr_root:
        logger.error(f"{timeoutput()} - ERROR: sonarr_root_folder and/or radarr_root_folder are required")
        return
    
    # Fetch data from Sonarr and Radarr
    logger.info(f"{timeoutput()} - Fetching data from Sonarr and Radarr...")
    
    sonarr_data = {}
    radarr_data = {}
    
    if config.get("sonarr"):
        for instance_name in tqdm(config["sonarr"].keys(), desc="Loading Sonarr instances"):
            sonarr_data.update(fetch_all_instances(config, "sonarr"))
    
    if config.get("radarr"):
        for instance_name in tqdm(config["radarr"].keys(), desc="Loading Radarr instances"):
            radarr_data.update(fetch_all_instances(config, "radarr"))
    
    total_sonarr = sum(len(items) for items in sonarr_data.values()) if sonarr_data else 0
    total_radarr = sum(len(items) for items in radarr_data.values()) if radarr_data else 0
    
    logger.info(f"{timeoutput()} - Loaded {total_sonarr} shows from Sonarr, {total_radarr} movies from Radarr")
    
    if total_sonarr == 0 and total_radarr == 0:
        logger.info(f"{timeoutput()} - No data found in Sonarr or Radarr. Exiting.")
        return
    
    # Fetch data from Plex
    logger.info(f"{timeoutput()} - Fetching data from Plex...")
    plex_data = fetch_plex_libraries(config)
    
    # Apply root folder mapping (like Gaparr's root_folder)
    plex_data_mapped = map_plex_paths(plex_data, sonarr_root, radarr_root, config)
    
    plex_movies = len(plex_data_mapped['movies'])
    plex_shows = len(plex_data_mapped['shows'])
    logger.info(f"{timeoutput()} - Loaded {plex_movies} movies and {plex_shows} TV shows from Plex")
    
    # Track statistics
    stats = {
        'movies_matched': 0,
        'movies_updated': 0,
        'movies_already_correct': 0,
        'movies_not_found': 0,
        'shows_matched': 0,
        'shows_updated': 0,
        'shows_already_correct': 0,
        'shows_not_found': 0
    }

    # ADD THIS: Track which Plex items have already been processed in this run
    processed_plex_items = {
        'movies': set(),  # Store ratingKeys
        'shows': set()
    }
    
    # Process Radarr movies against Plex
    logger.info(f"{timeoutput()} - Processing movies...")
    for instance_name, movies in radarr_data.items():
        for movie in tqdm(movies, desc=f"Checking {instance_name}"):
            arr_path = normalize_path(movie['path'])
            arr_id = movie['id']
            arr_title = movie['title']
            
            # For Radarr, only match if path starts with radarr_root_folder
            if radarr_root and not arr_path.startswith(normalize_path(radarr_root)):
                logger.debug(f"Skipping {arr_title}: path doesn't start with radarr_root_folder")
                stats['movies_not_found'] += 1
                continue
            
            # Remove root folder from path for matching
            match_path = arr_path.replace(normalize_path(radarr_root), "").lstrip('/')
            
            # Find matching Plex movie by path (search in mapped paths)
            plex_item = None
            for plex_path, plex_data_item in plex_data_mapped['movies'].items():
                # Normalize both paths for comparison
                normalized_plex_path = normalize_path(plex_path)
                normalized_match_path = normalize_path(match_path)
                
                # For movies, remove the filename from the plex path if it exists
                # Split path into parts
                plex_parts = normalized_plex_path.split('/')
                
                # Check if the last part contains a dot (likely a file with extension)
                if len(plex_parts) > 0 and '.' in plex_parts[-1] and not plex_parts[-1].startswith('.'):
                    # Remove the filename, keep only the directory path
                    plex_path_for_matching = '/'.join(plex_parts[:-1])
                else:
                    plex_path_for_matching = normalized_plex_path
                
                # Split into segments for comparison
                plex_segments = plex_path_for_matching.split('/')
                match_segments = normalized_match_path.split('/')
                
                # Check if the last segments match (most specific match)
                if len(match_segments) <= len(plex_segments):
                    if plex_segments[-len(match_segments):] == match_segments:
                        plex_item = plex_data_item
                        break
            
            if not plex_item:
                stats['movies_not_found'] += 1
                continue

            # ADD THIS: Check if this Plex item was already processed
            rating_key = plex_item['ratingKey']
            if rating_key in processed_plex_items['movies']:
                logger.debug(f"Skipping {arr_title}: Plex item already processed in this run")
                continue
            processed_plex_items['movies'].add(rating_key)

            stats['movies_matched'] += 1
            
            # Check if correct TMDB ID is already in Plex
            if arr_id in plex_item['tmdb_ids']:
                stats['movies_already_correct'] += 1
                continue

            # ADD THIS: Log mismatch with ID comparison
            logger.info(f"MISMATCH: '{arr_title}' - Radarr ID: {arr_id} vs Plex IDs: {plex_item['tmdb_ids']}")
            
            # Update Plex with correct TMDB ID
            success = update_plex_match(
                config,
                plex_item['ratingKey'],
                "movie",
                arr_id,
                arr_title,
                config.get('delay', 10)
            )
            
            if success:
                stats['movies_updated'] += 1
            else:
                logger.warning(f"{timeoutput()} - WARNING: Failed to update movie: {arr_title}")
    
    # Process Sonarr shows against Plex
    logger.info(f"{timeoutput()} - Processing TV shows...")
    for instance_name, shows in sonarr_data.items():
        for show in tqdm(shows, desc=f"Checking {instance_name}"):
            arr_path = normalize_path(show['path'])
            arr_id = show['id']
            arr_title = show['title']
            
            # For Sonarr, only match if path starts with sonarr_root_folder
            if sonarr_root and not arr_path.startswith(normalize_path(sonarr_root)):
                logger.debug(f"Skipping {arr_title}: path doesn't start with sonarr_root_folder")
                stats['shows_not_found'] += 1
                continue
            
            # Remove root folder from path for matching
            match_path = arr_path.replace(normalize_path(sonarr_root), "").lstrip('/')
            
            # Find matching Plex show by path (search in mapped paths)
            plex_item = None
            for plex_path, plex_data_item in plex_data_mapped['shows'].items():
                # Normalize both paths for comparison
                normalized_plex_path = normalize_path(plex_path)
                normalized_match_path = normalize_path(match_path)
                
                # Split into segments
                plex_segments = normalized_plex_path.split('/')
                match_segments = normalized_match_path.split('/')
                
                # Check if match_path segments match the end of plex_path segments
                if len(match_segments) <= len(plex_segments):
                    if plex_segments[-len(match_segments):] == match_segments:
                        plex_item = plex_data_item
                        break
            
            if not plex_item:
                stats['shows_not_found'] += 1
                continue
            
            # ADD THIS: Check if this Plex item was already processed
            rating_key = plex_item['ratingKey']
            if rating_key in processed_plex_items['shows']:
                logger.debug(f"Skipping {arr_title}: Plex item already processed in this run")
                continue
            processed_plex_items['shows'].add(rating_key)
            
            stats['shows_matched'] += 1
            
            # Check if correct TVDB ID is already in Plex
            if arr_id in plex_item['tvdb_ids']:
                stats['shows_already_correct'] += 1
                continue

            # ADD THIS: Log mismatch with ID comparison
            logger.info(f"MISMATCH: '{arr_title}' - Sonarr ID: {arr_id} vs Plex IDs: {plex_item['tvdb_ids']}")
            
            # Update Plex with correct TVDB ID
            success = update_plex_match(
                config,
                plex_item['ratingKey'],
                "show",
                arr_id,
                arr_title,
                config.get('delay', 10)
            )
            
            if success:
                stats['shows_updated'] += 1
            else:
                logger.warning(f"{timeoutput()} - WARNING: Failed to update show: {arr_title}")
    
    # Print summary to console and log
    total_time = round(time.time() - start_time, 2)

    summary = "\n" + "=" * 60 + "\n"
    summary += f"{timeoutput()} - Matcharr Complete!\n"
    summary += "=" * 60 + "\n"
    summary += "\nMOVIES:\n"
    summary += f"  Matched by path:     {stats['movies_matched']}\n"
    summary += f"  Already correct:     {stats['movies_already_correct']}\n"
    summary += f"  Updated:             {stats['movies_updated']}\n"
    summary += f"  Not found in Plex:   {stats['movies_not_found']}\n"
    summary += "\nTV SHOWS:\n"
    summary += f"  Matched by path:     {stats['shows_matched']}\n"
    summary += f"  Already correct:     {stats['shows_already_correct']}\n"
    summary += f"  Updated:             {stats['shows_updated']}\n"
    summary += f"  Not found in Plex:   {stats['shows_not_found']}\n"
    summary += "\n" + "=" * 60 + "\n"
    summary += f"{timeoutput()} - Total execution time: {total_time} seconds\n"
    summary += "=" * 60

    # Print to console
    print(summary)

    # Log to file
    for line in summary.split('\n'):
        if line.strip():
            logger.info(line)

    return  # <-- CHANGE THIS FROM sys.exit(0)


if __name__ == "__main__":
    from croniter import croniter
    from datetime import datetime, timedelta

    # Parse CRON_SCHEDULE and schedule accordingly
    try:
        # Validate the cron expression
        croniter(CRON_SCHEDULE)
        
        # Get the next run time
        base = datetime.now()
        iter = croniter(CRON_SCHEDULE, base)
        next_run = iter.get_next(datetime)
        
        # Schedule the job to run daily (schedule library limitation)
        # We'll check every minute and run when the cron matches
        logger.info(f"Scheduled to run at: {CRON_SCHEDULE}")
        logger.info(f"Next run at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        
    except (ValueError, IndexError) as e:
        logger.warning(f"Error parsing CRON_SCHEDULE '{CRON_SCHEDULE}': {e}. Using default: 02:00")
        CRON_SCHEDULE = "0 2 * * *"
    
    # Keep the script running
    logger.info("Matcharr is running in the background and will execute on schedule. Press Ctrl+C to stop.")
    
    # Custom cron checker
    def should_run():
        """Check if current time matches the cron schedule."""
        try:
            iter = croniter(CRON_SCHEDULE, datetime.now())
            # Get the previous run time
            prev = iter.get_prev(datetime)
            # Check if it was within the last minute
            return (datetime.now() - prev).seconds < 60
        except:
            return False

    last_run = None
    while True:
        now = datetime.now()
        if should_run() and (last_run is None or (now - last_run).seconds > 60):
            # Prevent multiple runs in the same minute
            last_run = now
            logger.info(f"Triggering scheduled run at {now.strftime('%Y-%m-%d %H:%M:%S')}")
            main()
        time.sleep(60)  # Check every minute