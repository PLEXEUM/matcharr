import requests
import json
import time
import logging


class Arr:
    def __init__(self, url, apikey, mediatype):
        self.data = self._request_with_retry(f"{url}/api/v3/{mediatype}/?apikey={apikey}")
        self.paths = self._request_with_retry(
            f"{url}/api/v3/rootfolder?apikey={apikey}",
            headers={"Accept": "application/json", "Content-Type": "application/json"}
        )
    
    def _request_with_retry(self, url, headers=None, retries=3):
        for attempt in range(1, retries + 1):
            try:
                r = requests.get(url, headers=headers, timeout=30)
                r.raise_for_status()
                return json.loads(r.text)
            except Exception as e:
                if attempt == retries:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
