"""
Matcharr - Compare Sonarr/Radarr data to Plex libraries and fix mismatches.
"""

import json
import time
import sys
from tqdm import tqdm
from datetime import datetime

from arr import fetch_all_instances
from plex import fetch_plex_libraries, normalize_plex_paths, update_plex_match, normalize_path


def timeoutput():
    """Return formatted timestamp for logging."""
    return datetime.now().strftime('%d %b %Y %H:%M:%S')


def main():
    start_time = time.time()
    
    print(f"{timeoutput()} - Starting Matcharr")
    
    # Load configuration
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"{timeoutput()} - ERROR: config.json not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"{timeoutput()} - ERROR: Invalid config.json: {e}")
        sys.exit(1)
    
    # Validate config
    if not config.get("plex_url") or not config.get("plex_token"):
        print(f"{timeoutput()} - ERROR: Plex URL and token are required")
        sys.exit(1)
    
    # Fetch data from Sonarr and Radarr
    print(f"{timeoutput()} - Fetching data from Sonarr and Radarr...")
    
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
    
    print(f"{timeoutput()} - Loaded {total_sonarr} shows from Sonarr, {total_radarr} movies from Radarr")
    
    if total_sonarr == 0 and total_radarr == 0:
        print(f"{timeoutput()} - No data found in Sonarr or Radarr. Exiting.")
        sys.exit(0)
    
    # Fetch data from Plex
    print(f"{timeoutput()} - Fetching data from Plex...")
    plex_data = fetch_plex_libraries(config)
    
    # Apply path mappings to Plex data
    plex_data_mapped = normalize_plex_paths(plex_data, config)
    
    plex_movies = len(plex_data_mapped['movies'])
    plex_shows = len(plex_data_mapped['shows'])
    print(f"{timeoutput()} - Loaded {plex_movies} movies and {plex_shows} TV shows from Plex")
    
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
    
    # Process Radarr movies against Plex
    print(f"{timeoutput()} - Processing movies...")
    for instance_name, movies in radarr_data.items():
        for movie in tqdm(movies, desc=f"Checking {instance_name}"):
            arr_path = normalize_path(movie['path'])
            arr_id = movie['id']
            arr_title = movie['title']
            
            # Find matching Plex movie by path
            plex_item = plex_data_mapped['movies'].get(arr_path)
            
            if not plex_item:
                stats['movies_not_found'] += 1
                continue
            
            stats['movies_matched'] += 1
            
            # Check if correct TMDB ID is already in Plex
            if arr_id in plex_item['tmdb_ids']:
                stats['movies_already_correct'] += 1
                continue
            
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
                print(f"{timeoutput()} - WARNING: Failed to update movie: {arr_title}")
    
    # Process Sonarr shows against Plex
    print(f"{timeoutput()} - Processing TV shows...")
    for instance_name, shows in sonarr_data.items():
        for show in tqdm(shows, desc=f"Checking {instance_name}"):
            arr_path = normalize_path(show['path'])
            arr_id = show['id']
            arr_title = show['title']
            
            # Find matching Plex show by path
            plex_item = plex_data_mapped['shows'].get(arr_path)
            
            if not plex_item:
                stats['shows_not_found'] += 1
                continue
            
            stats['shows_matched'] += 1
            
            # Check if correct TVDB ID is already in Plex
            if arr_id in plex_item['tvdb_ids']:
                stats['shows_already_correct'] += 1
                continue
            
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
                print(f"{timeoutput()} - WARNING: Failed to update show: {arr_title}")
    
    # Print summary
    total_time = round(time.time() - start_time, 2)
    
    print("\n" + "=" * 60)
    print(f"{timeoutput()} - Matcharr Complete!")
    print("=" * 60)
    print("\nMOVIES:")
    print(f"  Matched by path:     {stats['movies_matched']}")
    print(f"  Already correct:     {stats['movies_already_correct']}")
    print(f"  Updated:             {stats['movies_updated']}")
    print(f"  Not found in Plex:   {stats['movies_not_found']}")
    print("\nTV SHOWS:")
    print(f"  Matched by path:     {stats['shows_matched']}")
    print(f"  Already correct:     {stats['shows_already_correct']}")
    print(f"  Updated:             {stats['shows_updated']}")
    print(f"  Not found in Plex:   {stats['shows_not_found']}")
    print("\n" + "=" * 60)
    print(f"{timeoutput()} - Total execution time: {total_time} seconds")
    print("=" * 60)
    
    sys.exit(0)


if __name__ == "__main__":
    main()