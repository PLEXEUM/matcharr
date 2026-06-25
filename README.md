# 🔄 Matcharr

**Automatically fix Plex metadata mismatches using Sonarr and Radarr as the source of truth.**

Matcharr compares data from Sonarr/Radarr instances to libraries in Plex and fixes any mismatches created by the agents used. It ensures that:

- **Movies** in Plex use the correct **TMDB ID** from Radarr
- **TV Shows** in Plex use the correct **TVDB ID** from Sonarr

---

## How It Works

Matcharr runs as a persistent background service that automatically executes on a schedule:

1. **Scheduled Execution** - Runs automatically based on the `CRON_SCHEDULE` environment variable (default: daily at 2 AM)
2. Fetches all movies from Radarr (with TMDB IDs)
3. Fetches all TV shows from Sonarr (with TVDB IDs)
4. Fetches all movies and TV shows from Plex (with their current IDs)
5. Matches items by **path** (not by name - this is more reliable)
6. If a Plex item has the wrong ID or is missing the correct ID, it updates it
7. Reports statistics on what was matched, updated, or not found
8. Continues running and waits for the next scheduled execution

---

## Requirements

- Python 3.8+
- Docker (optional, recommended)
- Sonarr instance(s)
- Radarr instance(s)
- Plex instance with API token

---

## Installation

### Using Docker (Recommended)

1. Clone the repository:

```bash
git clone https://github.com/yourusername/matcharr.git
cd matcharr
```

2. Edit `config.json` with your settings (see Configuration below)

3. Run with Docker Compose:

```bash
docker-compose up -d
```

### Manual Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/matcharr.git
cd matcharr
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Edit `config.json` with your settings

4. Run:

```bash
python app.py
```

---

## Configuration

Create a `config.json` file with the following structure:

```json
{
  "plex_url": "https://plex.domain.tld",
  "plex_token": "your-plex-token",
  "delay": 10,
  "path_mappings": {
    "/mnt/unionfs/Media/": "/data/"
  },
  "radarr": {
    "radarr": {
      "url": "https://radarr.domain.tld",
      "apikey": "your-radarr-apikey"
    }
  },
  "sonarr": {
    "sonarr": {
      "url": "https://sonarr.domain.tld",
      "apikey": "your-sonarr-apikey"
    }
  }
}
```

---

## Configuration Options

| Option | Description |
|--------|-------------|
| `plex_url` | URL of your Plex server (e.g., https://plex.domain.tld) |
| `plex_token` | Your Plex API token ([how to find it](https://support.plex.tv/articles/204059436-finding-your-plex-token/)) |
| `delay` | Seconds to wait between Plex API calls (to avoid rate limiting) |
| `path_mappings` | Map paths from Sonarr/Radarr format to Plex format if they differ |
| `radarr` | One or more Radarr instances with unique names |
| `sonarr` | One or more Sonarr instances with unique names |

---

## Multiple Instances

You can add multiple Radarr and/or Sonarr instances:

```json
{
  "radarr": {
    "radarr": { "url": "https://radarr.domain.tld", "apikey": "..." },
    "radarr4k": { "url": "https://radarr4k.domain.tld", "apikey": "..." }
  },
  "sonarr": {
    "sonarr": { "url": "https://sonarr.domain.tld", "apikey": "..." },
    "sonarr4k": { "url": "https://sonarr4k.domain.tld", "apikey": "..." }
  }
}
```

---

## Path Mappings

Path mappings allow you to match paths when Sonarr/Radarr and Plex use different directory structures.

**Example:**

- Sonarr/Radarr uses: `/mnt/unionfs/Media/TV/Show/`
- Plex uses: `/data/TV/Show/`

Add this mapping:

```json
"path_mappings": {
  "/mnt/unionfs/Media/": "/data/"
}
```

---

## Scheduling

Matcharr runs continuously in the background and executes on a schedule defined by the `CRON_SCHEDULE` environment variable.

### CRON_SCHEDULE Format

The schedule follows standard cron syntax: `minute hour day month day_of_week`

| Field | Required | Values | Special Characters |
|-------|----------|--------|-------------------|
| Minute | Yes | 0-59 | * |
| Hour | Yes | 0-23 | * |
| Day of month | Yes (use *) | 1-31 | * |
| Month | Yes (use *) | 1-12 | * |
| Day of week | Yes (use *) | 0-6 (0=Sunday) | * |

> **Note:** Matcharr only supports daily scheduling (day, month, and day_of_week must be `*`).

### Examples

| CRON_SCHEDULE | Description |
|---------------|-------------|
| `0 2 * * *` | Run daily at 2:00 AM (default) |
| `30 4 * * *` | Run daily at 4:30 AM |
| `0 0 * * *` | Run daily at midnight |
| `15 3 * * *` | Run daily at 3:15 AM |

### Overriding the Schedule

You can override the schedule in your `docker-compose.yml`:

```yaml
environment:
  - TZ=America/New_York
  - CRON_SCHEDULE=30 4 * * *  # Run at 4:30 AM daily
```

---

## Assumptions / Limitations

- **Path-based matching only** - Matcharr matches by exact file path, not by name. Paths must match exactly (after normalization and mapping).
- **Movies** - Uses TMDB IDs from Radarr
- **TV Shows** - Uses TVDB IDs from Sonarr
- **Directory structure** - Assumes you're using the recommended Plex naming structure for movies and TV shows
- **No fuzzy matching** - If paths don't match exactly, items are skipped and reported as "Not found"
- **Plex only** - Emby is not supported (removed in v2.0)
- **Daily scheduling only** - Only daily schedules are supported (all fields except minute and hour must be `*`)

---

## Output

When Matcharr runs (either on schedule or manually), it will show:

- Log entries confirming the scheduled execution time
- Progress bars while loading data from Sonarr, Radarr, and Plex
- Progress bars while checking each instance against Plex
- A final summary showing:
  - How many items were matched by path
  - How many were already correct
  - How many were updated
  - How many were not found in Plex

All output is logged to `/app/logs/matcharr.log` for historical reference.

---

## Docker

The Docker image runs as a persistent service with scheduled execution. To use it:

```yaml
services:
  matcharr:
    image: plexeum/matcharr:latest
    container_name: matcharr
    restart: unless-stopped
    volumes:
      - ./config.json:/app/config.json:ro
      - ./logs:/app/logs
    environment:
      - TZ=America/New_York
      - CRON_SCHEDULE=0 2 * * *  # Run daily at 2:00 AM
```

> **Important:** The container will run continuously in the background and execute your scan at the scheduled time. It will NOT run on startup unless you specifically configure it to.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TZ` | Timezone for logging (e.g., America/New_York) |
| `CRON_SCHEDULE` | Cron schedule for automatic runs (default: `0 2 * * *` = 2 AM daily) |

---

## Troubleshooting

### Items Not Found in Plex

If items show as "Not found in Plex":

- Check that the path in Sonarr/Radarr matches the path in Plex
- Add path mappings to `config.json` if they differ
- Check for case sensitivity (paths are case-sensitive in Linux containers)

### Items Not Updating

If items are matched but not updating:

- Verify your Plex token has write permissions
- Check the `delay` value - too low may cause rate limiting
- Check Plex logs for API errors

### Schedule Not Running

If Matcharr isn't executing at the scheduled time:

- Check the container logs for scheduling confirmation: `docker logs matcharr | grep "Scheduled daily run"`
- Verify the `CRON_SCHEDULE` environment variable is set correctly in `docker-compose.yml`
- Ensure the container is running: `docker ps | grep matcharr`
- Check that the timezone (`TZ`) is correct for your location
- The schedule only supports daily runs (day, month, day_of_week must be `*`)

### Debugging

To see more detailed output, check the container logs:

```bash
docker logs matcharr
```

---

## License

MIT

---

## Contributing

Contributions are welcome! Please submit a pull request or open an issue.

---

**Matcharr** – Keep your Plex metadata in sync. 🔄