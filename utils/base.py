from datetime import datetime
from tqdm import tqdm


def timeoutput():
    now = datetime.now()
    return now.strftime('%d %b %Y %H:%M:%S')


def giefbar(iterator, desc):
    return tqdm(iterator, desc=f"{desc}:", bar_format="{desc:80} {percentage:3.0f}%|{bar}| {n_fmt:^5}/{total_fmt:^5} [{elapsed_s:5.0f} s]")


def map_path(config, path):
    """
    Map a path from Sonarr/Radarr format to Plex/Emby format.
    
    Args:
        config: Configuration dictionary containing path_mappings
        path: The path to map (from Sonarr/Radarr)
    
    Returns:
        The mapped path, or the original path if no mapping matches
    """
    for source_path, dest_path in config['path_mappings'].items():
        # Check if the input path starts with the source path
        if path.startswith(source_path):
            # Replace the source path with the destination path
            return path.replace(source_path, dest_path)
    return path