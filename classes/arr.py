import requests
import json


class Arr:
    def __init__(self, url, apikey, mediatype):
        # Get the actual media data (movies or series)
        r = requests.get(url=f"{url}/api/v3/{mediatype}/?apikey={apikey}")
        self.data = json.loads(r.text)

        # Get the actual paths for each media item
        # This gives us the full path for each movie/show
        self.paths = {}
        for item in self.data:
            # Use the item's ID as key and the path as value
            self.paths[item["id"]] = item["path"]