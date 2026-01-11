# SpaceX Launch Tracker

A Python application developed using Gradio that tracks and analyzes SpaceX launches using their public API with local caching, Docker support was planned initially but due to time constraints had to avoid.

## Installation
Clone the repository
Install the requirements
Run app by app.py file

## Usage

The application provides an interactive menu:

1. **Launch tracking**  - Display a list of all launches with key details.
                        - Allow users to filter launches based on:
                        - Date range
                        - Rocket name
                        - Launch success/failure
                        - Launch site
2. **Statistics** - Show rlaunch statistics
                  - Calculate success rates by rocket name
                  - Track the total number of launches for each launch site.
                  - Monitor launch frequency on a monthly and yearly basis.


### Backend terminal execution
```
SpaceX Launch Tracker
=====================

Using cached data (fresh within 24 hours)

Options:
1. View Statistics
2. Refresh Data
3. Exit

Enter choice (1-3): 
```

## Architecture

### Data Storage

- **Database**: SQLite (`/data/spacex_launches.db`)
- **Location**: `/data` directory 
- **Table schema**:
  - `launches` - Launch data with details
  - `cache_metadata` - Cache timestamps

### Caching Strategy

- Default cache lifetime: 24 hours
- Automatic refresh on expired cache
- Force refresh option available
- Database is empty

### API Integration

- **Endpoint**: `https://api.spacexdata.com/v4`
- **Resources**: launches( rockets, launchpads not used due to time constraints)
- **Error Handling**: error logging

## License

This project uses the SpaceX API which is publicly available. Please respect their usage guidelines.

## Resources

SpaceX API Documentation(https://github.com/r-spacex/SpaceX-API)
SpaceX API v4 Docs(https://github.com/r-spacex/SpaceX-API/tree/master/docs/v4)