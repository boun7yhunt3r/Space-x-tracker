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
    def __init__(self, db_path: str = "spacex_launches.db"):
        """Initialize tracker with database path.
        
        Args:
            db_path: Path to SQLite database (rework required for Docker)
        """
        self.api_base = "https://api.spacexdata.com/v4"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # launches table schema
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
        
    def _should_refresh_cache(self, cache_key: str, max_age_hours: int = 24) -> bool:
        """Check if cache needs to be refreshed based on timestamp      
        Args:
            cache_key: Cache identifier from metadata table
            max_age_hours: Maximum cache age in hours
            
        Returns:
            True if cache should be refreshed
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
        """Update cache metadata timestamp.
        
        Args:
            cache_key: Cache identifier
            data: Optional data to store
        """
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
            force_refresh: Force API call even if cache is fresh
            
        Returns:
            True if successful, False otherwise
        """
        if not force_refresh and not self._should_refresh_cache("launches"):
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
        """Calculate launch statistics from cached data.
        
        Returns:
            Dictionary with statistics
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
        
        # Launches by month (last 12 months)
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
        
        # Rocket launches breakdown (all statuses)
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
    
    def get_recent_launches(self, limit: int = 10) -> List[Dict]:
        """Get most recent launches.
        
        Args:
            limit: Number of launches to return
            
        Returns:
            List of launch dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, date_utc, success, rocket_name, launchpad_name, details
            FROM launches
            ORDER BY date_unix DESC
            LIMIT ?
        """, (limit,))
        
        columns = ['id', 'name', 'date_utc', 'success', 'rocket_name', 'launchpad_name', 'details']
        launches = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        
        return launches
    
    def get_launch_details(self, launch_id: str) -> Optional[Dict]:
        """Get detailed information about a specific launch.
        
        Args:
            launch_id: Launch identifier
            
        Returns:
            Launch details dictionary or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM launches WHERE id = ?", (launch_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        columns = ['id', 'name', 'date_utc', 'date_unix', 'success', 'details',
                   'rocket_id', 'rocket_name', 'launchpad_id', 'launchpad_name',
                   'crew', 'payloads', 'failures', 'links', 'fetched_at']
        
        launch = dict(zip(columns, row))
        
        # Parse JSON fields
        for field in ['crew', 'payloads', 'failures', 'links']:
            if launch[field]:
                launch[field] = json.loads(launch[field])
        
        return launch
    
    def search_launches(self, query: str) -> List[Dict]:
        """Search launches by name or details.
        
        Args:
            query: Search query
            
        Returns:
            List of matching launches
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, date_utc, success, rocket_name, details
            FROM launches
            WHERE name LIKE ? OR details LIKE ?
            ORDER BY date_unix DESC
        """, (f'%{query}%', f'%{query}%'))
        
        columns = ['id', 'name', 'date_utc', 'success', 'rocket_name', 'details']
        launches = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        
        return launches


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


def display_recent_launches(launches: List[Dict]):
    """Display recent launches."""
    print("\n" + "="*60)
    print("RECENT LAUNCHES")
    print("="*60 + "\n")
    
    for launch in launches:
        status = "✓ Success" if launch['success'] == 1 else "✗ Failed" if launch['success'] == 0 else "? Pending"
        date = datetime.fromisoformat(launch['date_utc'].replace('Z', '+00:00'))
        
        print(f"{launch['name']}")
        print(f"  Status: {status}")
        print(f"  Date: {date.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"  Rocket: {launch['rocket_name'] or 'Unknown'}")
        print(f"  Launchpad: {launch['launchpad_name'] or 'Unknown'}")
        if launch['details']:
            print(f"  Details: {launch['details'][:100]}...")
        print()


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
        print("2. View Recent Launches")
        print("3. Search Launches")
        print("4. Refresh Data")
        print("5. Exit")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == "1":
            stats = tracker.get_launch_statistics()
            display_statistics(stats)
        
        elif choice == "2":
            try:
                limit = int(input("How many launches to show? (default 10): ") or "10")
                launches = tracker.get_recent_launches(limit)
                display_recent_launches(launches)
            except ValueError:
                print("Invalid number")
        
        elif choice == "3":
            query = input("Enter search query: ").strip()
            if query:
                results = tracker.search_launches(query)
                if results:
                    display_recent_launches(results)
                else:
                    print("No launches found")
        
        elif choice == "4":
            tracker.fetch_launches(force_refresh=True)
        
        elif choice == "5":
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()