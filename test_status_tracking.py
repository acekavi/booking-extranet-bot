#!/usr/bin/env python3
"""
Test script to demonstrate the new status tracking functionality
"""

import os
import sys
import asyncio
from unittest.mock import Mock

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_manager import RateManager

async def test_status_tracking():
    """Test the status tracking functionality"""

    print("=" * 60)
    print("TESTING STATUS TRACKING FUNCTIONALITY")
    print("=" * 60)

    # Create a mock page object for testing
    mock_page = Mock()

    # Initialize RateManager
    rate_manager = RateManager(mock_page)

    print("\n1. Initial CSV Status:")
    print("-" * 30)
    progress = rate_manager.get_progress_summary()
    print(f"Total records: {progress['total_records']}")
    print(f"Completed: {progress['completed_records']}")
    print(f"Pending: {progress['pending_records']}")
    print(f"Progress: {progress['progress_percentage']}%")

    print("\n2. Sample room data (pending only):")
    print("-" * 40)
    first_room_id = None
    if rate_manager.csv_data:
        # Get data for first room
        first_room_id = rate_manager.csv_data[0]['Room ID']
        room_data = rate_manager.get_room_data_by_id(first_room_id)
        print(f"Room ID {first_room_id} has {len(room_data)} pending records")

        for record in room_data[:3]:  # Show first 3 records
            status = record.get('Status', 'pending')
            print(f"  - Date Range: {record['Date Range']}, Price: {record['Price']}, Status: {status}")

    print("\n3. Marking first record as completed:")
    print("-" * 45)
    if rate_manager.csv_data:
        first_record = rate_manager.csv_data[0]
        print(f"Marking as completed: Room {first_record['Room ID']}, Range {first_record['Date Range']}")
        rate_manager.mark_record_completed(first_record)

        # Show updated progress
        progress = rate_manager.get_progress_summary()
        print(f"Updated progress: {progress['completed_records']}/{progress['total_records']} ({progress['progress_percentage']}%)")

    print("\n4. Room data after marking one completed:")
    print("-" * 45)
    if rate_manager.csv_data and first_room_id:
        room_data = rate_manager.get_room_data_by_id(first_room_id)
        print(f"Room ID {first_room_id} now has {len(room_data)} pending records")

    print("\n5. To reset all statuses back to pending, you can use:")
    print("-" * 55)
    print("rate_manager.reset_all_status()")

    print("\n" + "=" * 60)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_status_tracking())
