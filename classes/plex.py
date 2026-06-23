import posixpath
import re


class Plex:
    def __init__(self, path, mappedpath, agent, metadataid, title, guids):
        self.agent = "unknown"
        self.id = 0
        self.path = path
        self.imdb = []
        self.tmdb = []
        self.tvdb = []

        # ALWAYS extract from guids first (more reliable)
        for guid in guids:
            guid_id = guid.id if hasattr(guid, 'id') else str(guid)
            if guid_id.startswith("imdb://"):
                match = re.search(r'(tt\d{7,})', guid_id)
                if match:
                    self.imdb.append(match.group())
            elif guid_id.startswith("tmdb://"):
                match = re.search(r'\d+', guid_id)
                if match:
                    self.tmdb.append(int(match.group()))
            elif guid_id.startswith("tvdb://"):
                match = re.search(r'\d+', guid_id)
                if match:
                    self.tvdb.append(int(match.group()))
            elif "imdb" in guid_id.lower():
                match = re.search(r'(tt\d{7,})', guid_id)
                if match:
                    self.imdb.append(match.group())
            elif "tmdb" in guid_id.lower():
                match = re.search(r'\d+', guid_id)
                if match:
                    self.tmdb.append(int(match.group()))
            elif "tvdb" in guid_id.lower():
                match = re.search(r'\d+', guid_id)
                if match:
                    self.tvdb.append(int(match.group()))

        # Then determine agent type and primary ID
        if agent.startswith("com.plexapp.agents.themoviedb") or "tmdb" in agent.lower():
            self.agent = "themoviedb"
            match = re.search(r'\d+', agent)
            if match:
                self.id = int(match.group())
            elif self.tmdb:
                self.id = self.tmdb[0]

        elif agent.startswith("com.plexapp.agents.thetvdb") or "tvdb" in agent.lower():
            self.agent = "thetvdb"
            match = re.search(r'\d+', agent)
            if match:
                self.id = int(match.group())
            elif self.tvdb:
                self.id = self.tvdb[0]

        elif agent.startswith("com.plexapp.agents.imdb") or "imdb" in agent.lower():
            self.agent = "imdb"
            match = re.search(r'(tt\d{7,})', agent)
            if match:
                self.id = match.group()
            elif self.imdb:
                self.id = self.imdb[0]

        elif agent.startswith("plex"):
            self.agent = "plex"
            # Use IDs already extracted from guids
            if self.tmdb:
                self.id = self.tmdb[0] if self.tmdb else 0
            elif self.tvdb:
                self.id = self.tvdb[0] if self.tvdb else 0

        # Handle mapped path
        if posixpath.isfile(mappedpath):
            self.mappedpath = posixpath.dirname(posixpath.abspath(mappedpath))
        else:
            self.mappedpath = mappedpath
            
        self.metadataid = metadataid
        self.title = title

    def to_dict(self):
        return {
            'title': self.title,
            'id': self.id,
            'metadataid': self.metadataid,
        }
