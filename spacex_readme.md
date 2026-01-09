# SpaceX Launch Tracker

A Python application that tracks and analyzes SpaceX launches using their public API with local caching and Docker support.

## Features

- **Data Management**
  - Fetches launch data from SpaceX API v4
  - SQLite database for local caching
  - Automatic cache refresh (24-hour default)
  - Works offline with cached data
  - Graceful error handling

- **Statistics & Analytics**
  - Total launches and success rate
  - Launches by year
  - Most used rockets
  - Launch search functionality

- **Docker Support**
  - Persistent data storage with volumes
  - Easy deployment and scaling
  - No data loss on container restart

## Installation

### Local Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python spacex_tracker.py
```

### Docker Installation

```bash
# Build and run with Docker Compose
docker-compose up -d

# Interact with the application
docker attach spacex-tracker

# Or build manually
docker build -t spacex-tracker .
docker run -it -v spacex-data:/data spacex-tracker
```

## Usage

The application provides an interactive menu:

1. **View Statistics** - Display overall launch statistics
2. **View Recent Launches** - Show recent launches with details
3. **Search Launches** - Search by mission name or details
4. **Refresh Data** - Force refresh from API
5. **Exit** - Close the application

### Example Session

```
SpaceX Launch Tracker
=====================

Fetching launches from SpaceX API...
Successfully cached 234 launches

Options:
1. View Statistics
2. View Recent Launches
3. Search Launches
4. Refresh Data
5. Exit

Enter choice (1-5): 1

============================================================
SPACEX LAUNCH STATISTICS
============================================================

Total Launches: 234
Successful: 210 (89.74%)
Failed: 14
Pending/Unknown: 10

--- Launches by Year ---
  2024: 98 launches
  2023: 96 launches
  2022: 61 launches
  2021: 31 launches
  2020: 26 launches
```

## Architecture

### Data Storage

- **Database**: SQLite (`/data/spacex_launches.db`)
- **Location**: `/data` directory (Docker volume mounted)
- **Schema**:
  - `launches` - Launch data with details
  - `cache_metadata` - Cache timestamps

### Caching Strategy

- Default cache lifetime: 24 hours
- Automatic refresh on expired cache
- Force refresh option available
- Offline mode with cached data

### API Integration

- **Endpoint**: `https://api.spacexdata.com/v4`
- **Resources**: launches, rockets, launchpads
- **Timeout**: 10 seconds
- **Error Handling**: Fallback to cached data

## Docker Volumes

Data persists in named Docker volumes:

```bash
# View volumes
docker volume ls

# Inspect volume
docker volume inspect spacex-tracker_spacex-data

# Backup database
docker run --rm -v spacex-tracker_spacex-data:/data -v $(pwd):/backup alpine tar czf /backup/spacex_backup.tar.gz /data

# Restore database
docker run --rm -v spacex-tracker_spacex-data:/data -v $(pwd):/backup alpine tar xzf /backup/spacex_backup.tar.gz -C /
```

## Configuration

### Custom Database Path

```python
# In your code
tracker = SpaceXTracker(db_path="/custom/path/spacex.db")
```

### Cache Refresh Interval

Modify `max_age_hours` parameter:

```python
# Check if cache older than 12 hours
self._should_refresh_cache("launches", max_age_hours=12)
```

## Development

### Project Structure

```
spacex-tracker/
├── spacex_tracker.py      # Main application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Docker Compose configuration
└── README.md            # Documentation
```

### Running Tests

```bash
# Test API connection
python -c "from spacex_tracker import SpaceXTracker; t = SpaceXTracker(); t.fetch_launches()"

# Test statistics
python -c "from spacex_tracker import SpaceXTracker; t = SpaceXTracker(); print(t.get_launch_statistics())"
```

## Troubleshooting

### API Connection Issues

- Check internet connectivity
- Verify API endpoint is accessible
- Application will use cached data automatically

### Docker Issues

```bash
# View logs
docker-compose logs -f

# Restart container
docker-compose restart

# Rebuild after code changes
docker-compose up -d --build
```

### Database Issues

```bash
# Check database exists
docker exec spacex-tracker ls -lh /data/

# Clear cache and refresh
docker exec spacex-tracker rm /data/spacex_launches.db
docker-compose restart
```

## API Reference

### SpaceXTracker Class

```python
tracker = SpaceXTracker(db_path="/data/spacex_launches.db")

# Fetch and cache launches
tracker.fetch_launches(force_refresh=False)

# Get statistics
stats = tracker.get_launch_statistics()

# Get recent launches
launches = tracker.get_recent_launches(limit=10)

# Get launch details
details = tracker.get_launch_details(launch_id="5eb87cd9ffd86e000604b32a")

# Search launches
results = tracker.search_launches(query="Starlink")
```

## License

This project uses the SpaceX API which is publicly available. Please respect their usage guidelines.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with Docker
5. Submit a pull request

## Resources

- [SpaceX API Documentation](https://github.com/r-spacex/SpaceX-API)
- [SpaceX API v4 Docs](https://github.com/r-spacex/SpaceX-API/tree/master/docs/v4)