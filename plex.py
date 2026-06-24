"""
Simple functions to fetch Plex data and update metadata.
"""

import re
import time
import os
import logging  # <-- ADD THIS LINE
import requests
from plexapi.server import PlexServer

# <-- ADD THIS LINE AFTER IMPORTS -->
logger = logging.getLogger(__name__)

def normalize_path(path):
    """Normalize path for consistent comparison."""
    if not path:
        return path
    normalized = os.path.normpath(path).replace('\\', '/')
    return normalized.rstrip('/')


# ===== ADD THIS FUNCTION HERE =====
def map_plex_paths(plex_data, sonarr_root, radarr_root, config):
    """
    Map Plex paths to match Arr root folder structure.
    Like Gaparr's root_folder approach.
    """
    mapped_data = {'movies': {}, 'shows': {}}
    
    # Normalize root paths
    sonarr_root_norm = normalize_path(sonarr_root) if sonarr_root else ""
    radarr_root_norm = normalize_path(radarr_root) if radarr_root else ""
    
    for media_type in ['movies', 'shows']:
        for original_path, item_data in plex_data[media_type].items():
            mapped_path = normalize_path(original_path)
            
            # Try to match against radarr_root_folder or sonarr_root_folder
            if media_type == 'movies' and radarr_root_norm:
                # If Plex path contains the radarr root, keep it as-is
                if radarr_root_norm in mapped_path:
                    mapped_data['movies'][mapped_path] = item_data
                    continue
            
            if media_type == 'shows' and sonarr_root_norm:
                # If Plex path contains the sonarr root, keep it as-is
                if sonarr_root_norm in mapped_path:
                    mapped_data['shows'][mapped_path] = item_data
                    continue
            
            # If no root mapping applies, still include the path
            mapped_data[media_type][mapped_path] = item_data
    
    return mapped_data
# ===== END OF ADDED FUNCTION =====


def fetch_plex_libraries(config):
    """
    Connect to Plex and fetch all movie and TV show libraries.
    
    Returns:
        Dictionary with library data: {
            'movies': {path: {'ratingKey': key, 'title': title, 'tmdb_ids': [ids], 'tvdb_ids': [ids]}},
            'shows': {path: {'ratingKey': key, 'title': title, 'tmdb_ids': [ids], 'tvdb_ids': [ids]}}
        }
    """
    server = PlexServer(config["plex_url"], config["plex_token"])
    sections = server.library.sections()
    
    result = {'movies': {}, 'shows': {}}
    
    for section in sections:
        if section.type == "movie":
            result['movies'] = _load_plex_items(section, "movie")
        elif section.type == "show":
            result['shows'] = _load_plex_items(section, "show")
    
    return result


def _load_plex_items(section, media_type):
    """Load items from a single Plex section."""
    items = {}
    for item in section.all():
        if not item.locations:
            continue
            
        path = normalize_path(item.locations[0])
        
        # Extract IDs from GUIDs
        tmdb_ids = []
        tvdb_ids = []
        imdb_ids = []
        
        for guid in item.guids:
            guid_str = str(guid.id) if hasattr(guid, 'id') else str(guid)
            
            # Extract TMDB ID
            tmdb_match = re.search(r'tmdb://(\d+)', guid_str)
            if tmdb_match:
                tmdb_ids.append(int(tmdb_match.group(1)))
            
            # Extract TVDB ID
            tvdb_match = re.search(r'tvdb://(\d+)', guid_str)
            if tvdb_match:
                tvdb_ids.append(int(tvdb_match.group(1)))
            
            # Extract IMDB ID
            imdb_match = re.search(r'imdb://(tt\d+)', guid_str)
            if imdb_match:
                imdb_ids.append(imdb_match.group(1))
        
        items[path] = {
            'ratingKey': item.ratingKey,
            'title': item.title,
            'tmdb_ids': tmdb_ids,
            'tvdb_ids': tvdb_ids,
            'imdb_ids': imdb_ids,
            'guid': item.guid,
            'type': media_type
        }
    
    return items


def update_plex_match(config, rating_key, media_type, media_id, title, delay):
    """
    Update a Plex item to use the correct TMDB or TVDB ID.
    
    Args:
        config: Configuration dictionary
        rating_key: Plex ratingKey of the item to update
        media_type: 'movie' or 'show'
        media_id: TMDB ID (for movies) or TVDB ID (for shows)
        title: Title of the media (for logging)
        delay: Seconds to wait after update
    
    Returns:
        True if successful, False otherwise
    """
    if media_type == "movie":
        guid = f"tmdb://{media_id}?lang=en"
        agent_type = "TMDB"
    else:  # show
        guid = f"tvdb://{media_id}?lang=en"
        agent_type = "TVDB"
    
    url = f"{config['plex_url']}/library/metadata/{rating_key}/match"
    params = {
        'X-Plex-Token': config['plex_token'],
        'guid': guid,
        'name': title  # <-- CHANGE 'title' TO 'name'
    }

    # Add proper headers (from your working code)
    headers = {
        "Accept": "application/json",
        "X-Plex-Product": "Matcharr",
        "X-Plex-Client-Identifier": "matcharr-695b47f5-3c61-4cbd-8eb3-bcc3d6d06ac5",
        "X-Plex-Version": "1.0.0",
    }

    # ===== ADD THIS DEBUG LINE HERE =====
    logger.debug(f"Attempting to match '{title}' (RatingKey: {rating_key}, {agent_type} ID: {media_id}) - URL: {url}")
    # ===== END DEBUG LINE =====
    
    for attempt in range(3):
        try:
            response = requests.put(url, params=params, timeout=30)
            
            if response.status_code == 200:
                print(f"✓ Updated {title} (RatingKey: {ratingKey}) to {agent_type} ID: {media_id}")
                time.sleep(delay)
                return True
            else:
                print(f"✗ Failed to update {title}: {response.status_code} - {response.text}")
                # Log the full request for debugging
                logger.debug(f"PUT {url} with params: {params}")
                logger.debug(f"Response: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            if attempt == 2:
                print(f"✗ Failed to update {title} after 3 attempts: {e}")
                return False
            time.sleep(2 ** attempt)
    
    return False


def normalize_plex_paths(plex_data, config):
    """
    Apply path mappings from config to normalize Plex paths.
    This allows matching if Sonarr/Radarr paths are different from Plex paths.
    
    Args:
        plex_data: Dictionary from fetch_plex_libraries()
        config: Configuration with path_mappings
    
    Returns:
        Same structure but with mapped paths as keys
    """
    mapped_data = {'movies': {}, 'shows': {}}
    
    for media_type in ['movies', 'shows']:
        for original_path, item_data in plex_data[media_type].items():
            mapped_path = original_path
            
            # Apply path mappings
            for source, dest in config.get('path_mappings', {}).items():
                if original_path.startswith(source):
                    mapped_path = original_path.replace(source, dest)
                    break
            
            mapped_path = normalize_path(mapped_path)
            mapped_data[media_type][mapped_path] = item_data
    
    return mapped_data