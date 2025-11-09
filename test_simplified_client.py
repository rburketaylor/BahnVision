#!/usr/bin/env python3
"""
Test script to verify simplified MVG client compatibility.
"""

import asyncio
import sys
from datetime import datetime, timezone
from typing import Any

# Add the backend directory to the path
sys.path.insert(0, '/home/burket/Git/BahnVision/backend')

from app.services.mvg_client import MVGClient as OriginalMVGClient
from app.services.mvg_client_simplified import MVGClient as SimplifiedMVGClient


def compare_mapping_functions():
    """Test that mapping functions produce identical results."""

    # Sample data that would come from MVG API
    sample_departure_data = {
        "planned": 1705320000,  # Jan 15, 2024 10:00 UTC
        "time": 1705320120,     # Jan 15, 2024 10:02 UTC
        "delay": 2,
        "platform": "1",
        "realtime": True,
        "line": "U3",
        "destination": "Fürstenried West",
        "type": "UBAHN",
        "icon": "mdi-subway",
        "cancelled": False,
        "messages": ["Message 1", "Message 2"]
    }

    sample_route_stop_data = {
        "station": {
            "id": "de:09162:6",
            "name": "Marienplatz",
            "place": "München",
            "latitude": 48.137,
            "longitude": 11.575
        },
        "plannedTime": 1705320000,
        "time": 1705320120,
        "platform": "1",
        "transportType": "UBAHN",
        "line": {
            "name": "U3",
            "destination": "Fürstenried West"
        },
        "delay": 2,
        "messages": []
    }

    sample_route_leg_data = {
        "departure": sample_route_stop_data,
        "arrival": {
            "station": {
                "id": "de:09162:70",
                "name": "Hauptbahnhof",
                "place": "München",
                "latitude": 48.140,
                "longitude": 11.558
            },
            "plannedTime": 1705320600,
            "time": 1705320600,
            "platform": "2"
        },
        "transportType": "UBAHN",
        "line": {
            "name": "U3",
            "destination": "Westendstraße"
        },
        "duration": 10,
        "distance": 1200,
        "intermediateStops": []
    }

    sample_route_plan_data = {
        "duration": 10,
        "transfers": 0,
        "departure": sample_route_stop_data,
        "arrival": {
            "station": {
                "id": "de:09162:70",
                "name": "Hauptbahnhof",
                "place": "München",
                "latitude": 48.140,
                "longitude": 11.558
            },
            "plannedTime": 1705320600,
            "time": 1705320600,
            "platform": "2"
        },
        "legs": [sample_route_leg_data]
    }

    # Test departure mapping
    original_departure = OriginalMVGClient._map_departure(sample_departure_data)
    simplified_departure = SimplifiedMVGClient()._map_departure(sample_departure_data)

    print("=== Departure Mapping Test ===")
    print(f"Original: {original_departure}")
    print(f"Simplified: {simplified_departure}")
    print(f"Departures match: {original_departure == simplified_departure}")
    print()

    # Test route stop mapping
    original_stop = OriginalMVGClient._map_route_stop(sample_route_stop_data)
    simplified_stop = SimplifiedMVGClient()._map_route_stop(sample_route_stop_data)

    print("=== Route Stop Mapping Test ===")
    print(f"Original: {original_stop}")
    print(f"Simplified: {simplified_stop}")
    print(f"Route stops match: {original_stop == simplified_stop}")
    print()

    # Test route leg mapping
    original_leg = OriginalMVGClient._map_route_leg(sample_route_leg_data)
    simplified_leg = SimplifiedMVGClient()._map_route_leg(sample_route_leg_data)

    print("=== Route Leg Mapping Test ===")
    print(f"Original: {original_leg}")
    print(f"Simplified: {simplified_leg}")
    print(f"Route legs match: {original_leg == simplified_leg}")
    print()

    # Test route plan mapping
    original_plan = OriginalMVGClient._map_route_plan(sample_route_plan_data)
    simplified_plan = SimplifiedMVGClient()._map_route_plan(sample_route_plan_data)

    print("=== Route Plan Mapping Test ===")
    print(f"Original: {original_plan}")
    print(f"Simplified: {simplified_plan}")
    print(f"Route plans match: {original_plan == simplified_plan}")
    print()

    # Test transport type parsing
    from app.services.mvg_client import parse_transport_types as original_parse
    from app.services.mvg_client_simplified import parse_transport_types as simplified_parse

    test_transport_types = ["UBAHN", "SBAHN", "BUS", "TRAM", "u-bahn", "s-bahn"]

    print("=== Transport Type Parsing Test ===")
    for transport_type in test_transport_types:
        try:
            original_result = original_parse([transport_type])
            simplified_result = simplified_parse([transport_type])
            match = original_result == simplified_result
            print(f"'{transport_type}': Original={original_result}, Simplified={simplified_result}, Match={match}")
        except Exception as e:
            print(f"'{transport_type}': Error - {e}")

    return True


def test_type_converters():
    """Test that type conversion functions behave identically."""
    from app.services.mvg_client_simplified import TypeConverter

    test_values = [
        None,
        "123",
        123,
        123.456,
        "invalid",
        {"minutes": 30},
        {"duration": 45},
        {"unknown": 10},
        1705320000,  # timestamp
    ]

    print("=== Type Conversion Test ===")
    for value in test_values:
        datetime_result = TypeConverter.to_datetime(value)
        int_result = TypeConverter.to_int(value)
        float_result = TypeConverter.to_float(value)
        minutes_result = TypeConverter.to_minutes(value)

        print(f"Input: {value}")
        print(f"  to_datetime: {datetime_result}")
        print(f"  to_int: {int_result}")
        print(f"  to_float: {float_result}")
        print(f"  to_minutes: {minutes_result}")
        print()


def test_field_extractor():
    """Test field extraction functionality."""
    from app.services.mvg_client_simplified import FieldExtractor

    sample_data = {
        "station": {
            "id": "de:09162:6",
            "name": "Marienplatz"
        },
        "transportType": "UBAHN",
        "line": {
            "name": "U3",
            "destination": "Fürstenried West"
        }
    }

    print("=== Field Extraction Test ===")

    # Test simple fallback
    result1 = FieldExtractor.get_with_fallbacks(sample_data, "station", "stop")
    print(f"get_with_fallbacks(station, stop): {result1}")

    # Test nested extraction
    result2 = FieldExtractor.get_nested_with_fallbacks(
        sample_data,
        [["line"], ["route"]],
        "name", "label", "symbol"
    )
    print(f"get_nested_with_fallbacks for line name: {result2}")

    # Test nested transport type extraction
    result3 = FieldExtractor.get_nested_with_fallbacks(
        sample_data,
        [["transportType"], ["product"], ["line", "transportType"]]
    )
    print(f"get_nested_with_fallbacks for transport type: {result3}")

    print()


if __name__ == "__main__":
    print("Testing Simplified MVG Client Compatibility")
    print("=" * 50)

    try:
        compare_mapping_functions()
        test_type_converters()
        test_field_extractor()

        print("=" * 50)
        print("All tests completed successfully!")

    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)