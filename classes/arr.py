import requests
import json


class Arr:
    def __init__(self, url, apikey, mediatype):
        # Get the actual media data (movies or series)
        r = requests.get(url=f"{url}/api/v3/{mediatype}/?apikey={apikey}")
        self.data = json.loads(r.text)

        # Get the actual paths for each media item
        # The API returns a list of objects, each with a 'path' field
        self.paths = [item.get("path") for item in self.data if item.get("path")]