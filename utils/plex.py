import os
import posixpath
import time
import requests
import requests.exceptions


from plexapi.video import Show
from plexapi.video import Movie
from classes.plex import Plex
from utils.base import timeoutput, giefbar, tqdm, map_path
from utils.logging import get_logger

logger = get_logger(__name__)

def normalize_path(path):
    """Normalize path for cross-platform comparison."""
    if not path:
        return path
    # Convert backslashes to forward slashes and normalize
    normalized = os.path.normpath(path).replace('\\', '/')
    # Remove trailing slash for consistent comparison
    return normalized.rstrip('/')

def load_plex_data(server, plex_sections, plexlibrary, config):
    for sectionid in plex_sections.values():
        section = server.library.sectionByID(sectionid)
        
        # DEBUG only - goes to file, not console
        logger.debug(f"Loading Plex section: {section.title} (ID: {sectionid}, Type: {section.type})")
        
        # Get the root items (shows for TV, movies for movies)
        if section.type == "show":
            from plexapi.video import Show
            media = [item for item in section.all(includeGuids=1) if isinstance(item, Show)]
            logger.debug(f"Loaded {len(media)} shows from TV section {section.title}")
        else:
            media = section.all(includeGuids=1)
            logger.debug(f"Loaded {len(media)} movies from Movie section {section.title}")
        
        # Debug first item to see what map_path returns
        if media:
            first_location = media[0].locations[0] if hasattr(media[0], 'locations') and media[0].locations else None
            if first_location:
                mapped = map_path(config, first_location)
                logger.debug(f"First Plex location: '{first_location}' -> mapped to: '{mapped}'")

        plexlibrary[sectionid] = []
        for row in giefbar(media, f'{timeoutput()} - Loading Plex section {section.title} (ID {sectionid})'):
            mapped_path = map_path(config, row.locations[0])
            logger.debug(f"mapped path for {row.title}: '{mapped_path}'")
            plexlibrary[sectionid].append(Plex(row.locations[0],
                                            mapped_path,
                                            row.guid,
                                            row.ratingKey,
                                            row.title,
                                            row.guids))
        

def check_duplicate(server, plex_sections, config, delay):
    duplicate = 0

    Show._include = ""
    Movie._include = ""
    for sectionid, mediatype in giefbar(plex_sections.items(), f'{timeoutput()} - Checking for duplicates in Plex'):
        section = server.library.sectionByID(int(sectionid))
        for item in section.all():
            if len(item.locations) > 1:
                dirname = posixpath.dirname(item.locations[0])
                for location in item.locations:
                    if posixpath.dirname(location) != dirname:
                        duplicate += 1
                        plex_split(item.ratingKey, config, delay)
                        time.sleep(delay)

    return duplicate


def arr_find_plex_id(arrpaths, arr_plex_match, plex_library_paths, plex_sections, config):
    # DEBUG only - goes to file
    logger.debug(f"Finding Plex IDs for arr paths")
    
    for arrtype in arrpaths.keys():
        logger.debug(f"Processing {arrtype} instances: {list(arrpaths[arrtype].keys())}")
        arr_plex_match[arrtype] = {}
        
        for arr in arrpaths[arrtype].keys():
            arr_plex_match[arrtype][arr] = {}
            logger.debug(f"Matching paths for {arr} ({len(arrpaths[arrtype][arr])} paths)")
            
            for arr_path in arrpaths[arrtype][arr].values():
                normalized_arr_path = normalize_path(arr_path)
                for library in plex_library_paths.keys():
                    for plex_path in plex_library_paths[library].values():
                        # Map and normalize both paths for comparison
                        mapped_plex_path = map_path(config, posixpath.join(plex_path, ''))
                        normalized_plex_path = normalize_path(mapped_plex_path)
                        
                        if normalized_arr_path == normalized_plex_path:
                            arr_plex_match[arrtype][arr][arr_path] = {"plex_library_id": library}
                            plex_sections[library] = library
                            logger.debug(f"Matched path: {arr_path} -> Plex library {library}")
                            break


def plex_compare_media(arr_plex_match, sonarr, radarr, library, config, delay):
    counter = 0
    
    # DEBUG only - goes to file
    total_sonarr = sum(len(items) for items in sonarr.values()) if sonarr else 0
    total_radarr = sum(len(items) for items in radarr.values()) if radarr else 0
    logger.debug(f"Starting comparison - Radarr movies: {total_radarr} items, Sonarr shows: {total_sonarr} items")
    logger.debug(f"Sonarr instances: {list(sonarr.keys()) if sonarr else []}")
    logger.debug(f"Radarr instances: {list(radarr.keys()) if radarr else []}")
    
    for arrtype in arr_plex_match.keys():
        if arrtype == "radarr":
            agent = "themoviedb"
            arr = radarr
            logger.debug(f"Comparing Radarr instances: {list(arr.keys()) if arr else []}")
        elif arrtype == "sonarr":
            agent = "thetvdb"
            arr = sonarr
            logger.debug(f"Comparing Sonarr instances: {list(arr.keys()) if arr else []}")
            
        for arrinstance in arr_plex_match[arrtype].keys():
            # Check if instance exists in arr data
            if arrinstance not in arr:
                logger.warning(f"Instance '{arrinstance}' not found in {arrtype} data - available: {list(arr.keys()) if arr else []}")
                continue
            
            logger.debug(f"Processing {arrinstance} with {len(arr[arrinstance])} items")
            
            if len(arr[arrinstance]) == 0:
                logger.warning(f"No items found for {arrinstance}")
                continue
            
            # Log first 5 Arr paths for debugging
            logger.debug(f"=== DEBUG: First 5 {arrtype} paths from {arrinstance} ===")
            for idx, item in enumerate(arr[arrinstance][:5]):
                logger.debug(f"  {idx}: {item.title} -> {item.mappedpath}")
                
            for folder in arr_plex_match[arrtype][arrinstance].values():
                logger.debug(f"Checking folder: {folder}")
                library_id = folder.get('plex_library_id')
                logger.debug(f"Library ID: {library_id}")
                
                if library_id not in library:
                    logger.warning(f"Library ID {library_id} not found in library data!")
                    continue
                    
                logger.debug(f"Library has {len(library[library_id])} items")

                # Build lookup maps from Plex library
                tmdb_lookup = {}
                tvdb_lookup = {}
                for plex_item in library[library_id]:
                    if plex_item.tmdb:
                        for tmdb_id in plex_item.tmdb:
                            tmdb_lookup[str(tmdb_id)] = plex_item
                    if plex_item.tvdb:
                        for tvdb_id in plex_item.tvdb:
                            tvdb_lookup[str(tvdb_id)] = plex_item
                logger.debug(f"Built TMDb lookup map with {len(tmdb_lookup)} entries")
                logger.debug(f"Built TVDB lookup map with {len(tvdb_lookup)} entries")
                
                # Log first 5 Plex paths for debugging
                logger.debug(f"=== DEBUG: First 5 Plex paths in library {library_id} ===")
                for idx, plex_item in enumerate(library[library_id][:5]):
                    logger.debug(f"  {idx}: {plex_item.title} -> {plex_item.mappedpath}")
                
                logger.debug(f"Arr items count: {len(arr[arrinstance])}")
                
                for items in giefbar(arr[arrinstance], f'{timeoutput()} - Checking Plex against {arrinstance}'):
                    # Look up by appropriate ID
                    if arrtype == "sonarr":
                        lookup = tvdb_lookup
                        id_type = "TVDB"
                    else:
                        lookup = tmdb_lookup
                        id_type = "TMDb"
    
                    matched = False
    
                    # Try ID lookup first
                    if str(items.id) in lookup:
                        plex_items = lookup[str(items.id)]
                        matched = True
    
                    # For Sonarr only: if no TVDB ID match, try title matching
                    if not matched and arrtype == "sonarr":
                        logger.debug(f"TVDB ID not found for '{items.title}', trying title match...")
                        for plex_item in library[library_id]:
                            if items.title.lower() == plex_item.title.lower():
                                plex_items = plex_item
                                matched = True
                                logger.debug(f"Found by title match: {items.title} -> {plex_items.title}")
                                break
    
                    if matched:
                        # ... rest of comparison logic (agent checks, plex_match calls, etc.)
            
                        # DEBUG only - goes to file
                        if arrtype == "sonarr":
                            logger.debug(f"Comparing: {items.title} (Sonarr TVDB ID: {items.id}) vs Plex: {plex_items.title} (Plex TVDB IDs: {plex_items.tvdb})")
                        elif arrtype == "radarr":
                            logger.debug(f"Comparing: {items.title} (Radarr TMDB ID: {items.id}) vs Plex: {plex_items.title} (Plex TMDB IDs: {plex_items.tmdb})")
            
                        if plex_items.agent == "imdb":
                            if items.imdb == plex_items.id:
                                continue
                            # Only WARNING+ shows in console, so these tqdm writes still show
                            tqdm.write(
                                f"{timeoutput()} - Plex metadata item {plex_items.metadataid} with imdb ID:{plex_items.id} did not match {arrinstance} imdb ID:{items.imdb}")
                            tqdm.write(
                                f"{timeoutput()} - Path: {items.mappedpath}")

                            try:
                                plex_match(config["plex_url"],
                                        config["plex_token"],
                                        "imdb",
                                        plex_items.metadataid,
                                        items.imdb,
                                        items.title,
                                        delay)

                                time.sleep(delay)
                            except TypeError:
                                tqdm.write(f"{timeoutput()} - Plex metadata ID appears to be missing.")
                            counter += 1

                        elif plex_items.agent == "plex":
                            match_found = 0
                            if arrtype == "radarr":
                                for tmdbid in plex_items.tmdb:
                                    if items.id == tmdbid:
                                        match_found = 1
                                        break
                                if not match_found:
                                    # WARNING shows in console and file
                                    logger.warning(f"MISMATCH (Movie): {items.title} (Arr ID: {items.id}) vs Plex TMDB IDs: {plex_items.tmdb}")
                                    tqdm.write(
                                        f"{timeoutput()} - Plex metadata item {plex_items.metadataid} with tmdb ID:{plex_items.tmdb} did not match {arrinstance} tmdb ID:{items.id}")
                                    tqdm.write(
                                        f"{timeoutput()} - Path: {items.mappedpath}")
                                    try:
                                        plex_match(config["plex_url"],
                                                config["plex_token"],
                                                "plextmdb",
                                                plex_items.metadataid,
                                                items.id,
                                                items.title,
                                                delay)
                                        time.sleep(delay)
                                    except TypeError:
                                        tqdm.write(f"{timeoutput()} - Plex metadata ID appears to be missing.")
                                    counter += 1
                
                            elif arrtype == "sonarr":
                                for tvdbid in plex_items.tvdb:
                                    if items.id == tvdbid:
                                        match_found = 1
                                        break
                                if not match_found:
                                    # WARNING shows in console and file
                                    logger.warning(f"MISMATCH (TV Show): {items.title} (Arr ID: {items.id}) vs Plex TVDB IDs: {plex_items.tvdb}")
                                    tqdm.write(
                                        f"{timeoutput()} - Plex metadata item {plex_items.metadataid} with tvdb ID:{plex_items.tvdb} did not match {arrinstance} tvdb ID:{items.id}")
                                    tqdm.write(
                                        f"{timeoutput()} - Path: {items.mappedpath}")
                                    try:
                                        plex_match(config["plex_url"],
                                                config["plex_token"],
                                                "plextvdb",
                                                plex_items.metadataid,
                                                items.id,
                                                items.title,
                                                delay)
                                        time.sleep(delay)
                                    except TypeError:
                                        tqdm.write(f"{timeoutput()} - Plex metadata ID appears to be missing.")
                                    counter += 1

                        else:
                            if items.id == plex_items.id:
                                continue
                            tqdm.write(f"{timeoutput()} - Plex metadata item {plex_items.metadataid} with {agent} ID:{plex_items.id} did not match {arrinstance} {agent} ID:{items.id}")
                            tqdm.write(f"{timeoutput()} - Path: {items.mappedpath}")
                            try:
                                plex_match(config["plex_url"],
                                        config["plex_token"],
                                        agent,
                                        plex_items.metadataid,
                                        items.id,
                                        items.title,
                                        delay)

                                time.sleep(delay)
                            except TypeError:
                                tqdm.write(f"{timeoutput()} - Plex metadata ID appears to be missing.")
                            counter += 1
                    else:
                        logger.debug(f"No Plex match found by {id_type} ID for: {items.title} (ID: {items.id})")
    
    return counter


# TODO add ability to use different language codes
def plex_match(url, token, agent, metadataid, agentid, title, delay):
    retries = 5
    while retries > 0:
        try:
            if agent == "plextmdb":
                url_params = {'X-Plex-Token': token,
                              'guid': f'tmdb://{agentid}?lang=en',
                              'name': title}
            elif agent == "plextvdb":
                url_params = {'X-Plex-Token': token,
                              'guid': f'tvdb://{agentid}?lang=en',
                              'name': title}
            else:
                url_params = {'X-Plex-Token': token,
                              'guid': f'com.plexapp.agents.{agent}://{agentid}?lang=en',
                              'name': title}

            url_str = f'{url}/library/metadata/{int(metadataid):d}/match'
            resp = requests.put(url_str, params=url_params, timeout=30)

            if resp.status_code == 200:
                tqdm.write(f"{timeoutput()} - Successfully matched {int(metadataid)} to {title} ({agentid})")
            else:
                tqdm.write(
                    f"{timeoutput()} - Failed to match {int(metadataid)} to {title} ({agentid}) - Plex returned error: {resp.text}")
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout):
            tqdm.write(
                f"{timeoutput()} - Exception matching {int(metadataid)} to {title} ({agentid}) - {retries} left.")
            retries -= 1
            time.sleep(delay)
    if retries == 0:
        raise Exception(
            f"{timeoutput()} - Exception matching {int(metadataid)} to {title} ({agentid}) - Ran out of retries.")


def plex_split(metadataid, config, delay):
    retries = 5
    while retries > 0:
        try:
            tqdm.write(f"{timeoutput()} - Checking for duplicate in Plex: Splitting item with ID:{metadataid}")
            url_params = {
                'X-Plex-Token': config["plex_token"]
            }
            url_str = '%s/library/metadata/%d/split' % (config["plex_url"], metadataid)
            resp = requests.put(url_str, params=url_params, timeout=30)

            if resp.status_code == 200:
                tqdm.write(f"{timeoutput()} - Checking for duplicate in Plex: Successfully split {metadataid}.")
            else:
                tqdm.write(f"{timeoutput()} - Checking for duplicate in Plex: Failed to split {metadataid} - Plex returned error: {resp.text}")
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout):
            tqdm.write(
                f"{timeoutput()} - Checking for duplicate in Plex: Exception splitting {metadataid} - {retries} left.")
            retries -= 1
            time.sleep(delay)
    if retries == 0:
        raise Exception(
            f"{timeoutput()} - Checking for duplicate in Plex: Exception splitting {metadataid} - Ran out of retries.")