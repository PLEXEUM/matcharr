import posixpath
import time
import requests
import requests.exceptions


from plexapi.video import Show
from plexapi.video import Movie
from classes.plex import Plex
from utils.base import timeoutput, giefbar, tqdm, map_path
from utils.logging import get_logger

# Setup logger
logger = get_logger(__name__)


def load_plex_data(server, plex_sections, plexlibrary, config):
    Show._include = ""
    Movie._include = ""
    for sectionid in plex_sections.values():
        section = server.library.sectionByID(sectionid)
        media = section.all()
        plexlibrary[sectionid] = [Plex(row.locations[0],
                                       map_path(config, row.locations[0]),
                                       row.guid,
                                       row.ratingKey,
                                       row.title,
                                       row.guids)
                                  for row in giefbar(media, f'{timeoutput()} - Loading Plex section {section.title} (ID {sectionid})')]


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
    for arrtype in arrpaths.keys():
        arr_plex_match[arrtype] = {}
        for arr in arrpaths[arrtype].keys():
            arr_plex_match[arrtype][arr] = {}
            for arr_path in arrpaths[arrtype][arr].values():
                # Normalize path for comparison
                arr_path_normalized = arr_path.replace('\\', '/').rstrip('/')
                for library in plex_library_paths.keys():
                    for plex_path in plex_library_paths[library].values():
                        plex_path_normalized = map_path(config, posixpath.join(plex_path, '')).replace('\\', '/').rstrip('/')
                        if arr_path_normalized == plex_path_normalized:
                            arr_plex_match[arrtype][arr][arr_path] = {"plex_library_id": library}
                            plex_sections[library] = library


def plex_compare_media(arr_plex_match, sonarr, radarr, library, config, delay):
    counter = 0
    total_compared = 0
    total_matched = 0
    total_skipped = 0
    mismatches_found = []

    # ============================================================
    # DEBUG: Print all Radarr paths
    # ============================================================
    print("\n" + "="*60)
    print("DEBUG: Radarr Paths Found")
    print("="*60)
    for arrtype in arr_plex_match.keys():
        if arrtype == "radarr":
            for arrinstance in arr_plex_match[arrtype].keys():
                for radarr_path in arr_plex_match[arrtype][arrinstance].keys():
                    print(f"  {radarr_path}")
    print("="*60)

    # ============================================================
    # DEBUG: Print all Plex paths (first 20)
    # ============================================================
    print("\n" + "="*60)
    print("DEBUG: Plex Paths Found (first 20)")
    print("="*60)
    for section_id, items in library.items():
        for item in items[:20]:  # Show first 20
            print(f"  {item.mappedpath}")
    print("="*60)

    # ============================================================
    # DEBUG: Print the path mapping
    # ============================================================
    print("\n" + "="*60)
    print("DEBUG: Path Mappings")
    print("="*60)
    for source, dest in config['path_mappings'].items():
        print(f"  {source} -> {dest}")
    print("="*60)

    # ============================================================
    # DEBUG: Specifically check Zombieland
    # ============================================================
    print("\n" + "="*60)
    print("DEBUG: Searching for Zombieland")
    print("="*60)

    # Check Radarr for Zombieland
    for arrtype in arr_plex_match.keys():
        if arrtype == "radarr":
            for arrinstance in arr_plex_match[arrtype].keys():
                for radarr_path in arr_plex_match[arrtype][arrinstance].keys():
                    if "Zombieland" in radarr_path:
                        print(f"FOUND in Radarr: {radarr_path}")

    # Check Plex for Zombieland
    for section_id, items in library.items():
        for item in items:
            if "Zombieland" in item.title:
                print(f"FOUND in Plex: {item.title} - {item.mappedpath}")
    print("="*60)
    print()

    logger.info("-" * 60)
    logger.info("Starting Plex comparison")
    logger.info("-" * 60)

    for arrtype in arr_plex_match.keys():
        if arrtype == "radarr":
            agent = "themoviedb"
            arr = radarr
            media_type = "Movie"
        elif arrtype == "sonarr":
            agent = "thetvdb"
            arr = sonarr
            media_type = "TV Show"

        for arrinstance in arr_plex_match[arrtype].keys():
            if len(arrinstance) == 0:
                continue

            logger.info(f"Checking {media_type}s from {arrinstance}")

            for folder in arr_plex_match[arrtype][arrinstance].values():
                for items in giefbar(arr[arrinstance], f'{timeoutput()} - Processing {media_type}s'):
                    total_compared += 1
                    matched = False
                    skipped = False

                    # Log progress every 100 items
                    if total_compared % 100 == 0:
                        logger.info(f"Progress: {total_compared} items checked")

                    for plex_items in library[folder.get("plex_library_id")]:
                        if items.mappedpath in [posixpath.dirname(plex_items.mappedpath), plex_items.mappedpath]:
                            if plex_items.agent == "imdb":
                                if items.imdb == plex_items.id:
                                    matched = True
                                    total_matched += 1
                                    break
                                else:
                                    mismatches_found.append({
                                        "title": items.title,
                                        "media_type": media_type,
                                        "arr_instance": arrinstance,
                                        "arr_id": items.imdb,
                                        "plex_id": plex_items.id,
                                        "path": items.mappedpath
                                    })
                                    logger.warning(f"MISMATCH: {items.title}")
                                    logger.warning(f"  IMDB ID: {items.imdb} vs Plex ID: {plex_items.id}")
                                    logger.warning(f"  Path: {items.mappedpath}")

                                    try:
                                        plex_match(config["plex_url"],
                                                   config["plex_token"],
                                                   "imdb",
                                                   plex_items.metadataid,
                                                   items.imdb,
                                                   items.title,
                                                   delay)
                                        counter += 1
                                        time.sleep(delay)
                                    except TypeError:
                                        logger.error(f"Plex metadata ID appears to be missing for {items.title}")
                                    break

                            elif plex_items.agent == "plex":
                                match_found = 0
                                if arrtype == "radarr":
                                    for tmdbid in plex_items.tmdb:
                                        if items.id == tmdbid:
                                            match_found = 1
                                            break
                                    if not match_found:
                                        mismatches_found.append({
                                            "title": items.title,
                                            "media_type": media_type,
                                            "arr_instance": arrinstance,
                                            "arr_id": items.id,
                                            "plex_id": plex_items.tmdb,
                                            "path": items.mappedpath
                                        })
                                        logger.warning(f"MISMATCH: {items.title}")
                                        logger.warning(f"  TMDB ID: {items.id} vs Plex ID: {plex_items.tmdb}")
                                        logger.warning(f"  Path: {items.mappedpath}")

                                        try:
                                            plex_match(config["plex_url"],
                                                       config["plex_token"],
                                                       "plextmdb",
                                                       plex_items.metadataid,
                                                       items.id,
                                                       items.title,
                                                       delay)
                                            counter += 1
                                            time.sleep(delay)
                                        except TypeError:
                                            logger.error(f"Plex metadata ID appears to be missing for {items.title}")
                                elif arrtype == "sonarr":
                                    for tvdbid in plex_items.tvdb:
                                        if items.id == tvdbid:
                                            match_found = 1
                                            break
                                    if not match_found:
                                        mismatches_found.append({
                                            "title": items.title,
                                            "media_type": media_type,
                                            "arr_instance": arrinstance,
                                            "arr_id": items.id,
                                            "plex_id": plex_items.tvdb,
                                            "path": items.mappedpath
                                        })
                                        logger.warning(f"MISMATCH: {items.title}")
                                        logger.warning(f"  TVDB ID: {items.id} vs Plex ID: {plex_items.tvdb}")
                                        logger.warning(f"  Path: {items.mappedpath}")

                                        try:
                                            plex_match(config["plex_url"],
                                                       config["plex_token"],
                                                       "plextvdb",
                                                       plex_items.metadataid,
                                                       items.id,
                                                       items.title,
                                                       delay)
                                            counter += 1
                                            time.sleep(delay)
                                        except TypeError:
                                            logger.error(f"Plex metadata ID appears to be missing for {items.title}")
                                break

                            else:
                                if items.id == plex_items.id:
                                    matched = True
                                    total_matched += 1
                                    break
                                else:
                                    mismatches_found.append({
                                        "title": items.title,
                                        "media_type": media_type,
                                        "arr_instance": arrinstance,
                                        "arr_id": items.id,
                                        "plex_id": plex_items.id,
                                        "path": items.mappedpath
                                    })
                                    logger.warning(f"MISMATCH: {items.title}")
                                    logger.warning(f"  {agent} ID: {items.id} vs Plex ID: {plex_items.id}")
                                    logger.warning(f"  Path: {items.mappedpath}")

                                    try:
                                        plex_match(config["plex_url"],
                                                   config["plex_token"],
                                                   agent,
                                                   plex_items.metadataid,
                                                   items.id,
                                                   items.title,
                                                   delay)
                                        counter += 1
                                        time.sleep(delay)
                                    except TypeError:
                                        logger.error(f"Plex metadata ID appears to be missing for {items.title}")
                                    break

    # Print final summary
    logger.info("-" * 60)
    logger.info("PLEX COMPARISON COMPLETE")
    logger.info("-" * 60)
    logger.info(f"Total items compared: {total_compared}")
    logger.info(f"Items already matched: {total_matched}")
    logger.info(f"Items fixed: {counter}")
    logger.info(f"Items skipped (no path match): {total_skipped}")
    logger.info(f"Mismatches detected: {len(mismatches_found)}")

    if mismatches_found:
        logger.info("-" * 60)
        logger.info("MISMATCH DETAILS (First 20)")
        logger.info("-" * 60)
        for i, mismatch in enumerate(mismatches_found[:20]):
            logger.info(f"{i+1}. {mismatch['media_type']}: {mismatch['title']}")
            logger.info(f"   Arr ID: {mismatch['arr_id']} | Plex ID: {mismatch['plex_id']}")
            logger.info(f"   Path: {mismatch['path']}")
        if len(mismatches_found) > 20:
            logger.info(f"   ... and {len(mismatches_found) - 20} more mismatches")

    logger.info("-" * 60)

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
                logger.info(f"Successfully matched {int(metadataid)} to {title} ({agentid})")
            else:
                logger.error(f"Failed to match {int(metadataid)} to {title} ({agentid}) - Plex returned error: {resp.text}")
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout):
            logger.warning(f"Exception matching {int(metadataid)} to {title} ({agentid}) - {retries} left.")
            retries -= 1
            time.sleep(delay)
    if retries == 0:
        raise Exception(
            f"Exception matching {int(metadataid)} to {title} ({agentid}) - Ran out of retries.")


def plex_split(metadataid, config, delay):
    retries = 5
    while retries > 0:
        try:
            logger.info(f"Checking for duplicate in Plex: Splitting item with ID:{metadataid}")
            url_params = {
                'X-Plex-Token': config["plex_token"]
            }
            url_str = '%s/library/metadata/%d/split' % (config["plex_url"], metadataid)
            resp = requests.put(url_str, params=url_params, timeout=30)

            if resp.status_code == 200:
                logger.info(f"Checking for duplicate in Plex: Successfully split {metadataid}.")
            else:
                logger.error(f"Checking for duplicate in Plex: Failed to split {metadataid} - Plex returned error: {resp.text}")
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout):
            logger.warning(f"Checking for duplicate in Plex: Exception splitting {metadataid} - {retries} left.")
            retries -= 1
            time.sleep(delay)
    if retries == 0:
        raise Exception(
            f"Checking for duplicate in Plex: Exception splitting {metadataid} - Ran out of retries.")