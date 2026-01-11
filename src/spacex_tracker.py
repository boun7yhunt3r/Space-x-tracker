import requests
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import sys

class SpaceXTracker:
    """Track and analyze SpaceX launches w/ local caching."""
    #def __init__(self, db_path: str = "./data/spacex_launches.db"):
    def __init__(self, db_path: str = r"data\spacex_launches.db"):
        """Initialize app with db path/ update for docker.
        
        Args:
            db_path: Path to SQLite database (rework required for Docker)
        """
        self.api_base = "https://api.spacexdata.com/v4"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite DB with required tables."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # table launches schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS launches (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    date_utc TEXT NOT NULL,
                    date_unix INTEGER NOT NULL,
                    success INTEGER,
                    details TEXT,
                    rocket_id TEXT,
                    rocket_name TEXT,
                    launchpad_id TEXT,
                    launchpad_name TEXT,
                    crew TEXT,
                    payloads TEXT,
                    failures TEXT,
                    links TEXT,
                    fetched_at TEXT NOT NULL
                )
            """)
            
            # last update timestamp tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    last_updated TEXT NOT NULL,
                    data TEXT
                )
            """)
            
            conn.commit()
            print(f"Database initialized at: {self.db_path.absolute()}")
            
        except Exception as e:
            print(f"Database initialization failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if conn:
                conn.close()
                
    def is_cache_empty(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM launches")
        count = cursor.fetchone()[0]
        conn.close()
        return count == 0
    
    def _should_refresh_cache(self, cache_key: str, max_age_hours: int = 24) -> bool:
        """Check if cache needs to be refreshed based on timestamp in cache_metadata     
        Args:
            cache_key: Cache identifier from metadata table
            max_age_hours: Maximum cache age in hours
            
        Returns:
            If cache should be refreshed returns True, else False
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT last_updated FROM cache_metadata WHERE key = ?",
            (cache_key,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return True
        
        last_updated = datetime.fromisoformat(result[0])
        return datetime.now() - last_updated > timedelta(hours=max_age_hours)
    
    def _update_cache_metadata(self, cache_key: str, data: Optional[str] = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO cache_metadata (key, last_updated, data)
            VALUES (?, ?, ?)
        """, (cache_key, datetime.now().isoformat(), data))
        
        conn.commit()
        conn.close()
    
    def get_cache_last_updated(self, cache_key: str = "launches") -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT last_updated FROM cache_metadata WHERE key = ?",
            (cache_key,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # Format nicely for UI
        dt = datetime.fromisoformat(row[0])
        return dt.strftime("%Y-%m-%d %H:%M UTC")

    def fetch_launches(self, force_refresh: bool = False) -> bool:
        """Fetch all launches from SpaceX API and cache locally.
        
        Args:
            force_refresh: Force API call even if cache is recently updated
            
        Returns:
            if successful True, else False 
        """
        if not force_refresh and not self._should_refresh_cache("launches") and not self.is_cache_empty():
            print("Using cached data (fresh within 24 hours)")
            return True
        
        try:
            print("Fetching launches from SpaceX API...")
            response = requests.get(f"{self.api_base}/launches", timeout=10)
            response.raise_for_status()
            launches = response.json()
            
            # print("\n--- SAMPLE API RESPONSE (first 5 launches) ---")
            # for i, launch in enumerate(launches[:2], start=1):
            #     print(f"\nLaunch #{i}")
            #     print(json.dumps(launch, indent=2))
            # print("\n--- END SAMPLE ---\n")

            # Fetch rockets for names
            rockets_response = requests.get(f"{self.api_base}/rockets", timeout=10)
            rockets = {r['id']: r['name'] for r in rockets_response.json()}
            
            # Fetch launchpads for names
            pads_response = requests.get(f"{self.api_base}/launchpads", timeout=10)
            launchpads = {p['id']: p['name'] for p in pads_response.json()}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for launch in launches:
                cursor.execute("""
                    INSERT OR REPLACE INTO launches VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    launch['id'],
                    launch['name'],
                    launch['date_utc'],
                    launch['date_unix'],
                    1 if launch.get('success') else 0 if launch.get('success') is False else None,
                    launch.get('details'),
                    launch.get('rocket'),
                    rockets.get(launch.get('rocket')),
                    launch.get('launchpad'),
                    launchpads.get(launch.get('launchpad')),
                    json.dumps(launch.get('crew', [])),
                    json.dumps(launch.get('payloads', [])),
                    json.dumps(launch.get('failures', [])),
                    json.dumps(launch.get('links', {})),
                    datetime.now().isoformat()
                ))
            
            conn.commit()
            conn.close()
            
            self._update_cache_metadata("launches")
            print(f"Successfully cached {len(launches)} launches")
            return True
            
        except requests.RequestException as e:
            print(f"API Error: {e}")
            print("Using existing cached data if available")
            return False
        except Exception as e:
            print(f"Error: {e}")
            return False
    
    def get_launch_statistics(self) -> Dict:
        """Calculate launch statistics from DB cached data.
        
        Returns:
            Dictionary with statistics on launch data
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total launches
        cursor.execute("SELECT COUNT(*) FROM launches")
        total = cursor.fetchone()[0]
        
        # Success rate
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN success IS NULL THEN 1 ELSE 0 END) as pending
            FROM launches
        """)
        successful, failed, pending = cursor.fetchone()
        
        # Launches by year
        cursor.execute("""
            SELECT strftime('%Y', date_utc) as year, COUNT(*) as count
            FROM launches
            GROUP BY year
            ORDER BY year DESC
        """)
        by_year = cursor.fetchall()
        
        # Launches by month
        cursor.execute("""
            SELECT strftime('%Y-%m', date_utc) as month, COUNT(*) as count
            FROM launches
            GROUP BY month
            ORDER BY month DESC
        """)
        by_month = cursor.fetchall()
        
        # Most used rockets
        cursor.execute("""
            SELECT rocket_name, COUNT(*) as count
            FROM launches
            WHERE rocket_name IS NOT NULL
            GROUP BY rocket_name
            ORDER BY count DESC
        """)
        by_rocket = cursor.fetchall()
        
        # Rocket launches breakdown (include every statuses)
        cursor.execute("""
            SELECT 
                rocket_name,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN success IS NULL THEN 1 ELSE 0 END) as pending
            FROM launches
            WHERE rocket_name IS NOT NULL
            GROUP BY rocket_name
        """)
        rocket_success_data = cursor.fetchall()
        by_rocket_success = {
            rocket: {
                'successful': successful,
                'failed': failed,
                'pending': pending
            }
            for rocket, successful, failed, pending in rocket_success_data
        }
        
        # Launches by launch site
        cursor.execute("""
            SELECT launchpad_name, COUNT(*) as count
            FROM launches
            WHERE launchpad_name IS NOT NULL
            GROUP BY launchpad_name
            ORDER BY count DESC
        """)
        by_launch_site = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            'total': total,
            'successful': successful or 0,
            'failed': failed or 0,
            'pending': pending or 0,
            'success_rate': round((successful or 0) / total * 100, 2) if total > 0 else 0,
            'by_year': by_year,
            'by_month': by_month,
            'by_rocket': by_rocket,
            'by_rocket_success': by_rocket_success,
            'by_launch_site': by_launch_site
        }

def display_statistics(stats: Dict):
    """Display formatted statistics."""
    print("\n" + "="*60)
    print("SPACEX LAUNCH STATISTICS")
    print("="*60)
    print(f"\nTotal Launches: {stats['total']}")
    print(f"Successful: {stats['successful']} ({stats['success_rate']}%)")
    print(f"Failed: {stats['failed']}")
    print(f"Pending/Unknown: {stats['pending']}")
    
    print("\n--- Launches by Year ---")
    for year, count in stats['by_year'][:5]:
        print(f"  {year}: {count} launches")
    
    print("\n--- Most Used Rockets ---")
    for rocket, count in stats['by_rocket'][:5]:
        print(f"  {rocket}: {count} launches")
    print("="*60 + "\n")


def main():
    """Main application entry point."""
    tracker = SpaceXTracker()
    
    print("SpaceX Launch Tracker")
    print("=====================\n")
    
    # Fetch latest data
    tracker.fetch_launches()
    
    while True:
        print("\nOptions:")
        print("1. View Statistics")
        print("2. Refresh Data")
        print("3. Exit")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            stats = tracker.get_launch_statistics()
            display_statistics(stats)
        
        elif choice == "2":
            tracker.fetch_launches(force_refresh=True)
        
        elif choice == "3":
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()