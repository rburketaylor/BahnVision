#!/usr/bin/env python3
"""Test script to verify the offset validation fix for 'from' parameter"""

import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from fastapi.testclient import TestClient

# Add the backend directory to the path so we can import app modules
sys.path.insert(0, 'backend')

from app.main import app

client = TestClient(app)

def test_from_parameter_offset_validation():
    """Test that 'from' parameter derived offset is validated against 240 minute limit"""

    # Test 1: Normal case - from_time within allowed range should work
    # 200 minutes from now should be acceptable
    future_time_within_limit = (datetime.now(timezone.utc) + timedelta(minutes=200)).isoformat()
    response = client.get(f"/api/v1/mvg/departures?station=de:09162:6&from={quote(future_time_within_limit)}")
    # This should not raise a validation error (though it might raise station not found)
    print(f"Test 1 - Within limit (200 min): Status {response.status_code}")
    assert response.status_code in [200, 404, 502, 503]  # Any valid response except 422

    # Test 2: Edge case - from_time exactly at 240 minutes should work
    future_time_at_limit = (datetime.now(timezone.utc) + timedelta(minutes=240)).isoformat()
    response = client.get(f"/api/v1/mvg/departures?station=de:09162:6&from={quote(future_time_at_limit)}")
    print(f"Test 2 - At limit (240 min): Status {response.status_code}")
    assert response.status_code in [200, 404, 502, 503]  # Any valid response except 422

    # Test 3: Violation case - from_time resulting in offset > 240 should raise 422
    future_time_exceeding_limit = (datetime.now(timezone.utc) + timedelta(minutes=300)).isoformat()
    response = client.get(f"/api/v1/mvg/departures?station=de:09162:6&from={quote(future_time_exceeding_limit)}")
    print(f"Test 3 - Exceeding limit (300 min): Status {response.status_code}")
    assert response.status_code == 422  # Should raise validation error

    # Verify the error message
    error_detail = response.json()
    print(f"Error message: {error_detail.get('detail')}")
    # Handle both string and list error formats
    error_msg = error_detail.get('detail')
    if isinstance(error_msg, list):
        error_msg = error_msg[0].get('msg', '') if error_msg else ''
    assert "offset derived from 'from' parameter exceeds maximum allowed value of 240 minutes" in str(error_msg).lower()

    # Test 4: Past time should work (results in offset = 0)
    past_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    response = client.get(f"/api/v1/mvg/departures?station=de:09162:6&from={quote(past_time)}")
    print(f"Test 4 - Past time (-30 min): Status {response.status_code}")
    assert response.status_code in [200, 404, 502, 503]  # Any valid response except 422

    print("\nAll tests passed! The offset validation fix is working correctly.")

if __name__ == "__main__":
    test_from_parameter_offset_validation()