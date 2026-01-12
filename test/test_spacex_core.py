import json
import sqlite3
import tempfile
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.spacex_tracker import SpaceXTracker
from app import SpaceXGradioApp


def load_test_data():
    """Load sample launch data for testing"""
    with open(Path(__file__).parent / "test_data.json") as f:
        return json.load(f)


class FakeAPI:
    """Simulates SpaceX API responses"""
    def __init__(self, data):
        self.data = data
    
    def json(self):
        return self.data
    
    def raise_for_status(self):
        pass


def fake_api_call(url, timeout=10):
    """Returns fsynthetic data instead of calling real API"""
    data = load_test_data()
    if "launches" in url:
        return FakeAPI(data["launches"])
    if "rockets" in url:
        return FakeAPI(data["rockets"])
    if "launchpads" in url:
        return FakeAPI(data["launchpads"])


# Test 1: Check that API data gets saved to database
def test_api_fetch():
    data = load_test_data()
    
    with patch("requests.get", side_effect=fake_api_call):
        tracker = SpaceXTracker(tempfile.mktemp())
        tracker.fetch_launches(force_refresh=True)
        
        # Count rows in database to verify data saved 
        conn = sqlite3.connect(tracker.db_path)
        count = conn.execute("SELECT COUNT(*) FROM launches").fetchone()[0]
        conn.close()
        
        assert count == len(data["launches"])


# Test 2: Check filtering works correctly
def test_filtering():
    data = load_test_data()
    
    with patch("requests.get", side_effect=fake_api_call):
        app = SpaceXGradioApp()
        filtered = app.filter_launches(
            start_date=None,
            end_date=None,
            rocket=data["filters"]["rocket"],
            status="All",
            launch_site="All"
        )
        
        # check if all results match the filter
        assert all(filtered["Rocket"] == data["filters"]["rocket"])


# Test 3: Check success rate calculation
def test_statistics():
    data = load_test_data()
    
    with patch("requests.get", side_effect=fake_api_call):
        tracker = SpaceXTracker(tempfile.mktemp())
        tracker.fetch_launches(force_refresh=True)
        stats = tracker.get_launch_statistics()
        
        # Calculate expected success rate
        successes = sum(1 for launch in data["launches"] if launch["success"])
        expected_rate = round(successes / len(data["launches"]) * 100, 2)
        
        assert stats["success_rate"] == expected_rate