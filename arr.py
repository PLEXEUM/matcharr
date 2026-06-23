"""
Simple functions to fetch data from Sonarr and Radarr instances.
"""

import requests
import time


def fetch_arr_data(url, apikey, mediatype):
    """
    Fetch all media items from a Sonarr or Radarr instance.
    
    Args:
        url: Base URL of the Arr instance
        apikey: API key for authentication
        mediatype: 'series' for Sonarr, 'movie' for Radarr
    
    Returns:
        List of media items with title, path, and ID
    """
    endpoint = f"{url}/api/v3/{mediatype}"
    params = {"apikey": apikey}
    
    for attempt in range(3):
        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Extract only what we need: title, path, and ID
            results = []
            for item in data:
                if mediatype == "series":
                    media_id = item.get("tvdbId")
                    imdb_id = item.get("imdbId", "")
                else:  # movie
                    media_id = item.get("tmdbId")
                    imdb_id = item.get("imdbId", "")
                
                results.append({
                    "title": item.get("title", ""),
                    "path": item.get("path", ""),
                    "id": media_id,
                    "imdb": imdb_id
                })
            
            return results
            
        except Exception as e:
            if attempt == 2:
                raise Exception(f"Failed to fetch from {url} after 3 attempts: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return []


def fetch_all_instances(config, arr_type):
    """
    Fetch data from all instances of a given type (sonarr or radarr).
    
    Args:
        config: Configuration dictionary
        arr_type: 'sonarr' or 'radarr'
    
    Returns:
        Dictionary with instance names as keys and lists of media as values
    """
    instances = config.get(arr_type, {})
    results = {}
    
    for instance_name, instance_config in instances.items():
        url = instance_config.get("url")
        apikey = instance_config.get("apikey")
        
        if not url or not apikey:
            continue
            
        mediatype = "series" if arr_type == "sonarr" else "movie"
        results[instance_name] = fetch_arr_data(url, apikey, mediatype)
    
    return results