"""
Matcharr compares data from Sonarr/Radarr instances to
libraries in Plex/Emby and fixes any mismatches created by the agents used.
"""

import json
import time
import sys
import os
import logging
import pkg_resources

from plexapi.server import PlexServer
from classes.arr import Arr
from classes.embydb import EmbyDB
from utils.emby import load_emby_data, arr_find_emby_id, emby_compare_media
from utils.plex import load_plex_data, check_duplicate, arr_find_plex_id, plex_compare_media
from utils.arr import parse_arr_data, get_arrpaths, check_faulty
from utils.base import timeoutput, giefbar
from utils.logging import get_logger

# ============================================================
# FORCE ALL OUTPUT TO STDOUT (Docker logs)
# ============================================================

# Ensure stdout/stderr go to Docker's log system
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

# Enable line buffering so logs appear immediately
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True)

# ============================================================
# FORCE LOG FILE CREATION - ALWAYS WRITE TO FILE
# ============================================================

# Create logs directory if it doesn't exist
os.makedirs("/app/logs", exist_ok=True)

# Define log file path
LOG_FILE = "/app/logs/matcharr.log"

# Write startup message directly to log file (bypasses logger)
with open(LOG_FILE, "a") as f:
    f.write("\n" + "="*60 + "\n")
    f.write(f"Matcharr Started - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("="*60 + "\n")
    f.flush()
    os.fsync(f.fileno())  # Force write to disk

# Setup logger (writes to both file and console)
logger = get_logger(__name__)

# Redirect stdout and stderr to also go to log file
class TeeLogger:
    def __init__(self, logger_obj, level):
        self.logger = logger_obj
        self.level = level
        self.terminal = sys.stdout

    def write(self, message):
        if message.strip():
            # Write to terminal
            self.terminal.write(message)
            # Write to log file via logger
            self.logger.log(self.level, message.strip())
            # Also write directly to file to ensure it's saved
            with open(LOG_FILE, "a") as f:
                f.write(message)
                f.flush()
                os.fsync(f.fileno())

    def flush(self):
        self.terminal.flush()

# Replace stdout and stderr
sys.stdout = TeeLogger(logger, logging.INFO)
sys.stderr = TeeLogger(logger, logging.ERROR)

# ============================================================
# MAIN APPLICATION
# ============================================================

runtime = time.time()

# Log startup - this goes to BOTH file AND Docker logs
print("="*60)
print("Matcharr Started")
print("="*60)

# Load configuration
config = json.load(open("config.json"))

# Log path mappings
print(f"Config loaded with {len(config['path_mappings'])} path mappings")
for source, dest in config['path_mappings'].items():
    print(f"  {source} -> {dest}")

# Check for required config fields
if "emby_enabled" not in config:
    config["emby_enabled"] = False
    print("emby_enabled not found in config, defaulting to False")
if "emby_token" not in config:
    config["emby_token"] = ""
if "emby_url" not in config:
    config["emby_url"] = "https://emby.domain.tld"

sonarr_config = config["sonarr"].keys()
radarr_config = config["radarr"].keys()
delay = config["delay"]
emby_enabled = config["emby_enabled"]
plex_enabled = config["plex_enabled"]
plex_sections, emby_sections, sonarrs_config, radarrs_config = dict(), dict(), dict(), dict()

for sonarr in sonarr_config:
    sonarrs_config[sonarr] = config["sonarr"][sonarr]

for radarr in radarr_config:
    radarrs_config[radarr] = config["radarr"][radarr]

if not bool(radarrs_config.keys()) and not bool(sonarrs_config.keys()):
    print("No Arrs configured - Exiting.")
    sys.exit(0)

# Load data from Arr instances.
media = {"sonarr": {}, "radarr": {}}
paths = {"sonarr": {}, "radarr": {}}

if bool(sonarrs_config.keys()):
    for sonarr in giefbar(sonarrs_config.keys(),
                          f'{timeoutput()} - Loading data from Sonarr instances'):
        media["sonarr"][sonarr] = Arr(sonarrs_config[sonarr]["url"],
                                      sonarrs_config[sonarr]["apikey"],
                                      "series").data
        paths["sonarr"][sonarr] = Arr(sonarrs_config[sonarr]["url"],
                                      sonarrs_config[sonarr]["apikey"],
                                      "series").paths

if bool(radarrs_config.keys()):
    for radarr in giefbar(radarrs_config.keys(),
                          f'{timeoutput()} - Loading data from Radarr instances'):
        media["radarr"][radarr] = Arr(radarrs_config[radarr]["url"],
                                      radarrs_config[radarr]["apikey"],
                                      "movie").data
        paths["radarr"][radarr] = Arr(radarrs_config[radarr]["url"],
                                      radarrs_config[radarr]["apikey"],
                                      "movie").paths

sonarr_items, radarr_items, plexlibrary, embylibrary = dict(), dict(), dict(), dict()

parse_arr_data(media, sonarr_items, radarr_items, config)
arrpaths = get_arrpaths(paths, config)

# Check for duplicate entries in Arr instances.
check_faulty(radarrs_config, sonarrs_config, radarr_items, sonarr_items)

if plex_enabled:
    # Load data from Plex.
    server = PlexServer(config["plex_url"], config["plex_token"])
    server_sections = server.library.sections()

    plex_library_paths, arr_plex_match = dict(), dict()

    for section in server_sections:
        plex_library_paths[section.key] = dict(enumerate(section.locations))
    arr_plex_match = {}
    arr_find_plex_id(arrpaths, arr_plex_match, plex_library_paths, plex_sections, config)

    # Check for duplicate entries in Plex.
    DUPLICATE = check_duplicate(server, plex_sections, config, delay)

    # Reload Plex data if duplicate items were found in Plex.
    if DUPLICATE > 0:
        plexlibrary = {}
        server.reload()

    load_plex_data(server, plex_sections, plexlibrary, config)

    # Check for mismatched entries and correct them.
    PLEX_FIXED_MATCHES = 0
    PLEX_FIXED_MATCHES += plex_compare_media(arr_plex_match,
                                             sonarr_items,
                                             radarr_items,
                                             plexlibrary,
                                             config,
                                             delay)
    print(f"Number of fixed matches in Plex: {PLEX_FIXED_MATCHES}")

if emby_enabled:
    # Load data from Emby.
    emby_library_paths = EmbyDB.libraries(config)
    emby_sections = EmbyDB.sections(config)
    load_emby_data(config, emby_sections, embylibrary)

    arr_emby_match = {}
    arr_find_emby_id(arrpaths, arr_emby_match, emby_library_paths, config)

    # Check for mismatched entries and correct them.
    EMBY_FIXED_MATCHES = 0
    EMBY_FIXED_MATCHES += emby_compare_media(arr_emby_match,
                                             sonarr_items,
                                             radarr_items,
                                             embylibrary,
                                             config)
    print(f"Number of fixed matches in Emby: {EMBY_FIXED_MATCHES}")

# Final summary
print("="*60)
print("SCAN COMPLETE")
print("="*60)

if plex_enabled:
    print(f"Plex movies checked: {len(plexlibrary.get(5, []))}")
    print(f"Plex TV shows checked: {len(plexlibrary.get(2, []))}")
    print(f"Total fixes applied: {PLEX_FIXED_MATCHES}")

if emby_enabled:
    print(f"Emby fixes applied: {EMBY_FIXED_MATCHES}")

print(f"Sonarr instances: {len(sonarrs_config)}")
print(f"Radarr instances: {len(radarrs_config)}")
print(f"Total run time: {round(time.time() - runtime, 2)} seconds")
print("="*60)

# Final flush to ensure all logs are written
with open(LOG_FILE, "a") as f:
    f.write(f"Run completed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.flush()
    os.fsync(f.fileno())

sys.exit(0)