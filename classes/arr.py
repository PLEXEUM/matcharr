import requests
import json


class Arr:
    def __init__(self, url, apikey, mediatype):
        # Get the actual media data (movies or series)
        r = requests.get(url=f"{url}/api/v3/{mediatype}/?apikey={apikey}")
        self.data = json.loads(r.text)

        # Get the actual paths for each media item
        self.paths = []
        for item in self.data:
            self.paths.append(item["path"])