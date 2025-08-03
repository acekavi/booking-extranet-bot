"""
Rate Management Module for Booking.com Extranet Bot

This module handles automated rate changes for different date ranges
in the Booking.com partner extranet calendar system.
"""

import asyncio
import logging
import csv
import os
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class RateManager:
    """
    Handles rate management operations for Booking.com extranet
    """

    def __init__(self, page: Page):
        """
        Initialize RateManager with a Playwright page instance

        Args:
            page: Active Playwright page instance from the main bot
        """
        self.page = page
        self.csv_data = []
        self.load_csv_data()

    async def human_delay(self, min_seconds: float = 3, max_seconds: float = 10, wait_for_network: bool = True) -> None:
        """
        Add a human-like random delay and optionally wait for network idle

        Args:
            min_seconds: Minimum delay in seconds
            max_seconds: Maximum delay in seconds
            wait_for_network: Whether to wait for network idle state
        """
        delay = random.uniform(min_seconds, max_seconds)
        logger.debug(f"Human delay: {delay:.1f} seconds")
        await asyncio.sleep(delay)

        if wait_for_network:
            try:
                await self.page.wait_for_load_state('networkidle', timeout=5000)
                logger.debug("Network idle state reached")
            except Exception as e:
                logger.debug(f"Network idle timeout (continuing): {e}")

    def load_csv_data(self) -> None:
        """
        Load pricing data from the CSV file and ensure Status column exists
        """
        try:
            self.csv_path = os.path.join(os.path.dirname(__file__), 'public', 'seasonal_room_prices_optimized.csv')

            with open(self.csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                self.csv_data = list(reader)

            # Check if Status column exists, if not add it
            if self.csv_data and 'Status' not in self.csv_data[0]:
                logger.info("Status column not found, adding it to all records")
                for record in self.csv_data:
                    record['Status'] = 'pending'
                self.save_csv_data()

            logger.info(f"Loaded {len(self.csv_data)} pricing records from CSV")

            # Log status summary
            completed_count = sum(1 for record in self.csv_data if record.get('Status', '').lower() == 'completed')
            pending_count = len(self.csv_data) - completed_count
            logger.info(f"Status summary: {completed_count} completed, {pending_count} pending")

        except Exception as e:
            logger.error(f"Failed to load CSV data: {e}")
            self.csv_data = []

    def save_csv_data(self) -> None:
        """
        Save the current CSV data back to the file
        """
        try:
            if not self.csv_data:
                logger.warning("No CSV data to save")
                return

            # Get the fieldnames from the first record
            fieldnames = list(self.csv_data[0].keys())

            # Write the data back to the CSV file
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.csv_data)

            logger.debug("CSV data saved successfully")

        except Exception as e:
            logger.error(f"Failed to save CSV data: {e}")

    def mark_record_completed(self, record: Dict) -> None:
        """
        Mark a specific record as completed in the CSV data

        Args:
            record: The record dictionary to mark as completed
        """
        try:
            # Find the record in csv_data and mark it as completed
            for i, csv_record in enumerate(self.csv_data):
                if (csv_record['Room ID'] == record['Room ID'] and
                    csv_record['Date Range'] == record['Date Range'] and
                    csv_record['Price'] == record['Price']):
                    self.csv_data[i]['Status'] = 'completed'
                    logger.info(f"Marked record as completed: Room {record['Room ID']}, Range {record['Date Range']}")
                    break

            # Save the updated data
            self.save_csv_data()

        except Exception as e:
            logger.error(f"Failed to mark record as completed: {e}")

    def get_progress_summary(self) -> Dict:
        """
        Get a summary of the current processing progress

        Returns:
            Dict with progress information
        """
        try:
            total_records = len(self.csv_data)
            completed_records = sum(1 for record in self.csv_data if record.get('Status', '').lower() == 'completed')
            pending_records = total_records - completed_records

            progress_percentage = (completed_records / total_records * 100) if total_records > 0 else 0

            summary = {
                'total_records': total_records,
                'completed_records': completed_records,
                'pending_records': pending_records,
                'progress_percentage': round(progress_percentage, 2)
            }

            logger.info(f"Progress Summary: {completed_records}/{total_records} completed ({progress_percentage:.1f}%)")
            return summary

        except Exception as e:
            logger.error(f"Failed to get progress summary: {e}")
            return {}

    def reset_all_status(self) -> bool:
        """
        Reset all records status back to 'pending' (useful for reprocessing)

        Returns:
            bool: True if reset successful
        """
        try:
            logger.info("Resetting all record statuses to 'pending'")

            for record in self.csv_data:
                record['Status'] = 'pending'

            self.save_csv_data()

            logger.info(f"Successfully reset {len(self.csv_data)} records to pending status")
            return True

        except Exception as e:
            logger.error(f"Failed to reset all statuses: {e}")
            return False

    def parse_date_range(self, date_range_str: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Parse date range string from CSV format to datetime objects

        Args:
            date_range_str: Date range in format "May 1 – September 30"

        Returns:
            Tuple of start_date and end_date as datetime objects, or (None, None) if parsing fails
        """
        try:
            # Handle different dash characters
            date_range_str = date_range_str.replace('–', '-').replace('—', '-')

            # Split the date range
            start_str, end_str = date_range_str.split(' - ')

            # Get current year
            current_year = datetime.now().year

            # Parse start date
            start_date = datetime.strptime(f"{start_str} {current_year}", "%B %d %Y")

            # Parse end date
            end_date = datetime.strptime(f"{end_str} {current_year}", "%B %d %Y")

            # If start date is after end date, end date is in next year
            if start_date > end_date:
                end_date = end_date.replace(year=current_year + 1)

            # Handle dates that go into 2027 - cap at 2027-01-01
            if end_date.year > 2026 or (end_date.year == 2027 and end_date.month >= 1):
                logger.info(f"End date {end_date} is beyond 2027-01-01, adjusting to 2027-01-01")
                end_date = end_date.replace(year=2027, month=1, day=1)

            return start_date, end_date
        except Exception as e:
            logger.error(f"Failed to parse date range '{date_range_str}': {e}")
            return None, None

    def get_room_data_by_id(self, room_id: str) -> List[Dict]:
        """
        Get all pending (not completed) pricing data for a specific room ID

        Args:
            room_id: Room ID to filter by

        Returns:
            List of pending pricing records for the room
        """
        pending_records = []
        for record in self.csv_data:
            if (record['Room ID'] == room_id and
                record.get('Status', '').lower() != 'completed'):
                pending_records.append(record)

        logger.info(f"Found {len(pending_records)} pending records for room ID {room_id}")
        return pending_records

    async def navigate_to_calendar(self) -> bool:
        """
        Navigate to the rates and availability calendar using the correct navigation

        Returns:
            bool: True if navigation successful, False otherwise
        """
        try:
            logger.info("Navigating to rates & availability calendar...")

            # First click on the "Rates & availability" navigation item to show dropdown
            availability_nav = 'li[data-nav-tag="availability"] button'
            await self.page.wait_for_selector(availability_nav, timeout=10000)
            await self.page.click(availability_nav)
            logger.info("Clicked on Rates & availability navigation item")

            # Wait for dropdown to appear and then click on Calendar
            await asyncio.sleep(1)  # Brief pause for dropdown to show

            calendar_link = 'li[data-nav-tag="availability_calendar"] a'
            await self.page.wait_for_selector(calendar_link, timeout=5000)
            await self.page.click(calendar_link)
            logger.info("Clicked on Calendar submenu item")

            # Wait for calendar page to load
            await self.page.wait_for_load_state('networkidle', timeout=15000)

            logger.info("Successfully navigated to calendar page")
            return True

        except Exception as e:
            logger.error(f"Failed to navigate to calendar: {e}")
            return False

    async def check_calendar_loaded(self) -> bool:
        """
        Check if the calendar page has loaded properly

        Returns:
            bool: True if calendar is loaded and ready
        """
        try:
            # Wait for calendar elements to be present
            calendar_selectors = [
                '.calendar',
                '.calendar-container',
                '[data-testid="calendar"]',
                '.rate-calendar',
                '.availability-calendar'
            ]

            for selector in calendar_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=3000)
                    logger.info(f"Calendar loaded - found element: {selector}")
                    return True
                except:
                    continue

            logger.warning("Calendar elements not found with standard selectors")
            return False

        except Exception as e:
            logger.error(f"Error checking calendar load status: {e}")
            return False

    async def get_current_page_info(self) -> Dict:
        """
        Get information about the current page for debugging

        Returns:
            Dict with page information
        """
        try:
            page_info = await self.page.evaluate('''
                () => {
                    return {
                        url: window.location.href,
                        title: document.title,
                        has_calendar: !!document.querySelector('.calendar, .calendar-container, [data-testid="calendar"]'),
                        visible_elements: Array.from(document.querySelectorAll('[class*="calendar"], [class*="rate"], [class*="availability"]')).map(el => el.className).slice(0, 10)
                    };
                }
            ''')

            logger.info(f"Current page info: {page_info}")
            return page_info

        except Exception as e:
            logger.error(f"Error getting page info: {e}")
            return {}

    async def process_all_rooms(self) -> bool:
        """
        Process all rooms found on the calendar page

        Returns:
            bool: True if all rooms processed successfully
        """
        try:
            logger.info("Starting to process all rooms...")

            # Show initial progress summary
            progress = self.get_progress_summary()
            logger.info(f"Initial progress: {progress['completed_records']}/{progress['total_records']} records completed ({progress['progress_percentage']}%)")

            # Find all room containers
            room_containers = await self.page.query_selector_all('.av-cal-list-room__name-row')
            logger.info(f"Found {len(room_containers)} rooms to process")

            if not room_containers:
                logger.warning("No room containers found")
                return False

            for i, room_container in enumerate(room_containers):
                try:
                    # Extract room information
                    room_info = await self.extract_room_info(room_container)
                    if not room_info:
                        logger.warning(f"Could not extract info for room {i+1}")
                        continue

                    # Check if this room has any pending records
                    pending_records = self.get_room_data_by_id(room_info['id'])
                    if not pending_records:
                        logger.info(f"Skipping room {room_info['name']} - no pending records")
                        continue

                    logger.info(f"Processing room: {room_info['name']} (ID: {room_info['id']}) - {len(pending_records)} pending records")

                    # Process this room
                    success = await self.process_single_room(room_container, room_info)
                    if not success:
                        logger.error(f"Failed to process room {room_info['name']}")
                        continue

                    logger.info(f"Successfully processed room: {room_info['name']}")

                    # Show updated progress
                    progress = self.get_progress_summary()
                    logger.info(f"Updated progress: {progress['completed_records']}/{progress['total_records']} records completed ({progress['progress_percentage']}%)")

                    # Small delay between rooms to avoid overwhelming the system
                    await self.human_delay(4, 8, wait_for_network=True)  # Human-like delay between rooms

                except Exception as e:
                    logger.error(f"Error processing room {i+1}: {e}")
                    continue

            # Show final progress summary
            final_progress = self.get_progress_summary()
            logger.info("=" * 60)
            logger.info("FINAL PROCESSING SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total records: {final_progress['total_records']}")
            logger.info(f"Completed records: {final_progress['completed_records']}")
            logger.info(f"Pending records: {final_progress['pending_records']}")
            logger.info(f"Completion percentage: {final_progress['progress_percentage']}%")
            logger.info("=" * 60)
            logger.info("Completed processing all rooms")
            return True

        except Exception as e:
            logger.error(f"Error in process_all_rooms: {e}")
            return False

    async def extract_room_info(self, room_container) -> Optional[Dict]:
        """
        Extract room name and ID from a room container element

        Args:
            room_container: Playwright element for the room container

        Returns:
            Dict with room name and ID, or None if extraction fails
        """
        try:
            # Extract room name and ID
            room_name_element = await room_container.query_selector('.av-cal-list-room__name')
            if not room_name_element:
                return None

            room_text = await room_name_element.inner_text()

            # Parse room name and ID from text like "Double Room with Garden View (Room ID: 1106898201)"
            if '(Room ID:' in room_text:
                room_name = room_text.split('(Room ID:')[0].strip()
                room_id = room_text.split('(Room ID:')[1].replace(')', '').strip()
            else:
                logger.warning(f"Could not parse room ID from text: {room_text}")
                return None

            return {
                'name': room_name,
                'id': room_id,
                'text': room_text
            }

        except Exception as e:
            logger.error(f"Error extracting room info: {e}")
            return None

    async def process_single_room(self, room_container, room_info: Dict) -> bool:
        """
        Process a single room by clicking bulk edit and updating rates

        Args:
            room_container: Playwright element for the room container
            room_info: Dict with room information

        Returns:
            bool: True if processing successful
        """
        try:
            # Find and click the bulk edit button
            bulk_edit_button = await room_container.query_selector('button.bui-button--primary')
            if not bulk_edit_button:
                logger.error(f"Bulk edit button not found for room {room_info['name']}")
                return False

            # Verify button text
            button_text = await bulk_edit_button.inner_text()
            if 'Bulk edit' not in button_text:
                logger.warning(f"Button text doesn't match expected 'Bulk edit': {button_text}")

            logger.info(f"Clicking bulk edit button for room {room_info['name']}")
            await bulk_edit_button.click()

            # Wait for modal to appear
            await self.human_delay(3, 5, wait_for_network=True)

            # Process the modal
            success = await self.handle_bulk_edit_modal(room_info)

            if success:
                logger.info(f"Successfully processed bulk edit for room {room_info['name']}")
            else:
                logger.error(f"Failed to process bulk edit modal for room {room_info['name']}")

            return success

        except Exception as e:
            logger.error(f"Error processing single room {room_info['name']}: {e}")
            return False

    async def handle_bulk_edit_modal(self, room_info: Dict) -> bool:
        """
        Handle the bulk edit modal for a specific room

        Args:
            room_info: Dict with room information

        Returns:
            bool: True if modal processed successfully
        """
        try:
            # Wait for modal to fully load
            logger.info(f"Waiting for bulk edit modal to load for room {room_info['name']}")

            # Wait for modal to appear - try multiple selectors
            modal_selectors = [
                '.av-general-modal',
                '.modal',
                '[role="dialog"]',
                '.bui-modal',
                '.av-general-modal__content'
            ]

            modal_loaded = False
            for selector in modal_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    logger.info(f"Modal loaded - found element: {selector}")
                    modal_loaded = True
                    break
                except:
                    continue

            if not modal_loaded:
                logger.error("Modal did not load properly")
                return False

            # Get room data from CSV (only pending records)
            room_data = self.get_room_data_by_id(room_info['id'])
            if not room_data:
                logger.info(f"No pending CSV data found for room ID {room_info['id']}")
                await self.close_modal_emergency()
                return True  # No pending data is not an error

            logger.info(f"Found {len(room_data)} pending pricing records for room {room_info['name']}")

            # Filter out date ranges that are before today
            today = datetime.now().date()
            valid_room_data = []

            for record in room_data:
                start_date, end_date = self.parse_date_range(record['Date Range'])
                if start_date and end_date:
                    # Skip if the entire date range is before today
                    if end_date.date() < today:
                        logger.info(f"Skipping date range {record['Date Range']} - entirely before today")
                        continue
                    # Adjust start date if it's before today
                    if start_date.date() < today:
                        logger.info(f"Adjusting start date for range {record['Date Range']} to today")
                    valid_room_data.append(record)
                else:
                    logger.warning(f"Skipping invalid date range: {record['Date Range']}")

            if not valid_room_data:
                logger.warning(f"No valid date ranges found for room {room_info['name']}")
                await self.close_modal_emergency()
                return True  # Not an error, just no valid data

            logger.info(f"Processing {len(valid_room_data)} valid date ranges for room {room_info['name']}")

            # Process each date range separately - close and reopen modal for each
            for i, record in enumerate(valid_room_data):
                logger.info(f"Processing date range {i+1}/{len(valid_room_data)} for room {room_info['name']}")

                # For the first date range, we already have the modal open
                if i == 0:
                    success = await self.process_date_range_in_modal(record)
                else:
                    # Close the current modal
                    logger.info("Closing modal before processing next date range")
                    await self.close_modal_emergency()
                    await asyncio.sleep(2)  # Wait for modal to close

                    # Reopen the modal by clicking bulk edit again
                    logger.info("Reopening modal for next date range")
                    success = await self.reopen_modal_and_process(room_info, record)

                if not success:
                    logger.error(f"Failed to process date range for record: {record}")
                    await self.close_modal_emergency()
                    return False

                # Mark this record as completed after successful processing
                logger.info(f"Marking record as completed: Room {record['Room ID']}, Range {record['Date Range']}")
                self.mark_record_completed(record)

                # Small delay between date range updates
                await self.human_delay(4, 8, wait_for_network=True)  # Human-like delay to prevent overwhelming the system

            # Close the final modal
            logger.info("Closing final modal after all date ranges processed")
            await self.close_modal_emergency()
            await asyncio.sleep(2)

            logger.info(f"Successfully completed bulk edit for room {room_info['name']}")
            return True

        except Exception as e:
            logger.error(f"Error handling bulk edit modal: {e}")
            await self.close_modal_emergency()
            return False

    async def reopen_modal_and_process(self, room_info: Dict, record: Dict) -> bool:
        """
        Reopen the bulk edit modal and process a single date range record

        Args:
            room_info: Dict with room information
            record: CSV record with pricing information

        Returns:
            bool: True if successfully processed
        """
        try:
            # Find the room container again
            room_containers = await self.page.query_selector_all('.av-cal-list-room__name-row')
            target_room_container = None

            for room_container in room_containers:
                try:
                    extracted_info = await self.extract_room_info(room_container)
                    if extracted_info and extracted_info['id'] == room_info['id']:
                        target_room_container = room_container
                        break
                except:
                    continue

            if not target_room_container:
                logger.error(f"Could not find room container for {room_info['name']}")
                return False

            # Click bulk edit button
            bulk_edit_button = await target_room_container.query_selector('button.bui-button--primary')
            if not bulk_edit_button:
                logger.error(f"Bulk edit button not found for room {room_info['name']}")
                return False

            logger.info(f"Reopening bulk edit modal for room {room_info['name']}")
            await bulk_edit_button.click()
            await self.human_delay(4, 6, wait_for_network=True)  # Wait for modal to load

            # Wait for modal to appear
            modal_selectors = [
                '.av-general-modal',
                '.modal',
                '[role="dialog"]',
                '.bui-modal',
                '.av-general-modal__content'
            ]

            modal_loaded = False
            for selector in modal_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    logger.info(f"Modal reopened - found element: {selector}")
                    modal_loaded = True
                    break
                except:
                    continue

            if not modal_loaded:
                logger.error("Modal did not reopen properly")
                return False

            # Process the date range
            success = await self.process_date_range_in_modal(record)

            # Note: The record will be marked as completed in the calling method
            # (handle_bulk_edit_modal) to avoid duplicate marking

            return success

        except Exception as e:
            logger.error(f"Error reopening modal and processing: {e}")
            return False

    async def click_save_changes_button(self, context: str = "accordion") -> bool:
        """
        Find and click an enabled "Save changes" button

        Args:
            context: Context description for logging purposes

        Returns:
            bool: True if save button was found and clicked successfully
        """
        try:
            logger.info(f"Looking for 'Save changes' button in {context}")

            save_button_selectors = [
                'button:has-text("Save changes")',
                'button:text("Save changes")',
                '.bui-button:has-text("Save changes")',
                '[type="submit"]:has-text("Save changes")'
            ]

            save_button = None
            for selector in save_button_selectors:
                try:
                    # Find all buttons matching this selector
                    buttons = await self.page.query_selector_all(selector)

                    # Look for an enabled and visible button
                    for button in buttons:
                        if (await button.is_visible() and
                            await button.is_enabled() and
                            not await button.is_disabled()):
                            save_button = button
                            break

                    if save_button:
                        break
                except:
                    continue

            if not save_button:
                logger.error(f"Could not find enabled 'Save changes' button in {context}")
                return False

            logger.info(f"Clicking 'Save changes' button in {context}")
            await save_button.click()

            # Human-like delay and wait for network idle
            await self.human_delay(3, 8, wait_for_network=True)

            # Check for error messages after save
            success = await self.check_for_save_errors(context)
            if not success:
                logger.error(f"Save operation failed with error in {context}")
                return False

            logger.info(f"Successfully clicked 'Save changes' button in {context}")
            return True

        except Exception as e:
            logger.error(f"Error clicking 'Save changes' button in {context}: {e}")
            return False

    async def check_for_save_errors(self, context: str) -> bool:
        """
        Check for error messages after a save operation

        Args:
            context: Context description for logging purposes

        Returns:
            bool: True if no errors found, False if errors detected
        """
        try:
            # Wait a moment for any error messages to appear
            await asyncio.sleep(2)

            # Check for common error message patterns
            error_selectors = [
                ':has-text("Whoops! Something went wrong")',
            ]

            for selector in error_selectors:
                try:
                    error_elements = await self.page.query_selector_all(selector)
                    for error_element in error_elements:
                        if await error_element.is_visible():
                            error_text = await error_element.inner_text()
                            logger.error(f"Error detected in {context}: {error_text}")
                            return False
                except:
                    continue

            return True

        except Exception as e:
            logger.error(f"Error checking for save errors in {context}: {e}")
            return True  # Assume no error if we can't check

    async def close_modal_emergency(self) -> None:
        """
        Emergency modal close function using multiple methods
        """
        try:
            logger.warning("Attempting to close modal")

            # Try close button first
            try:
                close_button = await self.page.query_selector('button.av-general-modal__close')
                if close_button and await close_button.is_visible():
                    await close_button.click()
                    await asyncio.sleep(2)
                    logger.info("Modal closed using close button")
                    return
            except:
                pass

            # Try escape key
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(2)
            logger.info("Modal closed using Escape key")

            # Try clicking outside modal
            try:
                await self.page.click('body', position={'x': 10, 'y': 10})
                await asyncio.sleep(1)
            except:
                pass

        except Exception as e:
            logger.error(f"Emergency modal close failed: {e}")

    async def process_date_range_in_modal(self, record: Dict) -> bool:
        """
        Process a specific date range record in the bulk edit modal

        Args:
            record: CSV record with pricing information

        Returns:
            bool: True if date range processed successfully
        """
        try:
            logger.info(f"=====================================")
            logger.info(f"Processing date range: {record['Date Range']}")
            logger.info(f"Room: {record['Room Name']} (ID: {record['Room ID']})")
            logger.info(f"Price: {record['Price']}")
            logger.info(f"Number of Rooms: {record['Number of Rooms']}")
            logger.info(f"=====================================")

            # Parse date range
            start_date, end_date = self.parse_date_range(record['Date Range'])
            if not start_date or not end_date:
                logger.error(f"Failed to parse date range: {record['Date Range']}")
                return False

            # Ensure dates are from today onwards and don't go beyond 2026
            today = datetime.now()
            if end_date.date() < today.date():
                logger.warning(f"Skipping date range {record['Date Range']} - entirely before today")
                return True  # Skip this range but don't fail

            if start_date.date() < today.date():
                start_date = today
                logger.info(f"Adjusted start date to today: {start_date.strftime('%Y-%m-%d')}")

            # Don't process dates beyond 2027-01-01
            cutoff_date = datetime(2027, 1, 1)
            if start_date >= cutoff_date:
                logger.warning(f"Skipping date range {record['Date Range']} - starts on or after 2027-01-01")
                return True  # Skip this range but don't fail

            if end_date > cutoff_date:
                end_date = cutoff_date
                logger.info(f"Adjusted end date to 2027-01-01: {end_date.strftime('%Y-%m-%d')}")

            # Step 1: Select date range in modal
            logger.info("Step 1: Setting date range...")
            success = await self.select_date_range_in_modal(start_date, end_date)
            if not success:
                logger.error("Failed to select date range in modal")
                return False
            logger.info("✓ Date range set successfully")

            # Step 2: Set number of rooms to sell
            logger.info("Step 2: Setting rooms to sell...")
            success = await self.set_rooms_to_sell(record['Number of Rooms'])
            if not success:
                logger.error("Failed to set rooms to sell")
                return False
            logger.info("✓ Rooms to sell set successfully")

            # Step 3: Select rate plan and set price
            logger.info("Step 3: Setting rate plan and price...")
            success = await self.set_rate_plan_and_price(record['Price'])
            if not success:
                logger.error("Failed to set rate plan and price")
                return False
            logger.info("✓ Rate plan and price set successfully")

            # Step 4: Set room status to open
            logger.info("Step 4: Setting room status to open...")
            success = await self.set_room_status_open()
            if not success:
                logger.error("Failed to set room status to open")
                return False
            logger.info("✓ Room status set to open successfully")

            # Save and close this date range processing
            logger.info("Step 5: Saving and closing for this date range...")
            success = await self.close_edit_modal()
            if not success:
                logger.error("Failed to save and close modal for this date range")
                return False
            logger.info("✓ Modal saved and closed successfully")

            logger.info(f"✓ Completed processing date range: {record['Date Range']}")
            logger.info(f"=====================================")

            return True

        except Exception as e:
            logger.error(f"Error processing date range in modal: {e}")
            return False

    async def select_date_range_in_modal(self, start_date: datetime, end_date: datetime) -> bool:
        """
        Select date range in the bulk edit modal

        Args:
            start_date: Start date to select
            end_date: End date to select

        Returns:
            bool: True if date range selected successfully
        """
        try:
            # Format dates to YYYY-MM-DD format as required
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')

            logger.info(f"Setting date range: {start_date_str} to {end_date_str}")

            # Clear and set start date
            start_date_input = await self.page.query_selector('input#date-from')
            if not start_date_input:
                logger.error("Start date input field not found")
                return False

            # Clear the input first
            await start_date_input.click()
            await self.page.keyboard.press('Control+a')  # Select all
            await self.page.keyboard.press('Delete')     # Delete selected text
            await asyncio.sleep(0.5)

            # Type the start date
            await start_date_input.type(start_date_str, delay=random.randint(40, 80))
            await self.human_delay(0.8, 1.5, wait_for_network=False)
            logger.info(f"Start date set to: {start_date_str}")

            # Clear and set end date
            end_date_input = await self.page.query_selector('input#date-to')
            if not end_date_input:
                logger.error("End date input field not found")
                return False

            # Clear the input first
            await end_date_input.click()
            await self.page.keyboard.press('Control+a')  # Select all
            await self.page.keyboard.press('Delete')     # Delete selected text
            await self.human_delay(0.5, 1, wait_for_network=False)

            # Type the end date
            await end_date_input.type(end_date_str, delay=random.randint(40, 80))
            await self.human_delay(0.8, 1.5, wait_for_network=False)
            logger.info(f"End date set to: {end_date_str}")

            # Optional: Press Tab or click elsewhere to trigger any date validation
            await end_date_input.press('Tab')
            await self.human_delay(1, 2, wait_for_network=True)
            return True

        except Exception as e:
            logger.error(f"Error selecting date range in modal: {e}")
            return False

    async def set_rooms_to_sell(self, num_rooms: str) -> bool:
        """
        Set the number of rooms to sell in the modal

        Args:
            num_rooms: Number of rooms to sell

        Returns:
            bool: True if rooms to sell set successfully
        """
        try:
            logger.info(f"Setting rooms to sell: {num_rooms}")

            # Step 1: Find and click the "Rooms to sell" button to open accordion
            rooms_to_sell_button = None
            button_selectors = [
                'button:has-text("Rooms to sell")',
                'button:text("Rooms to sell")',
                '[role="button"]:has-text("Rooms to sell")',
                'button[aria-expanded="false"]:has-text("Rooms to sell")'
            ]

            for selector in button_selectors:
                try:
                    rooms_to_sell_button = await self.page.query_selector(selector)
                    if rooms_to_sell_button and await rooms_to_sell_button.is_visible():
                        break
                except:
                    continue

            if not rooms_to_sell_button:
                logger.error("Could not find 'Rooms to sell' button")
                return False

            logger.info("Clicking 'Rooms to sell' button to open accordion")
            await rooms_to_sell_button.click()
            await self.human_delay(2, 4, wait_for_network=False)  # Wait for accordion to open

            # Step 2: Find and input the number of rooms in the opened accordion
            rooms_input = await self.page.query_selector('input#single-rts-input')
            if not rooms_input:
                logger.error("Could not find rooms input field after opening accordion")
                return False

            # Clear existing value and input new number
            await rooms_input.click()
            await self.page.keyboard.press('Control+a')  # Select all
            await self.page.keyboard.press('Delete')     # Delete selected text
            await self.human_delay(0.5, 1, wait_for_network=False)

            await rooms_input.type(str(num_rooms), delay=random.randint(30, 70))
            logger.info(f"Input number of rooms: {num_rooms}")

            # Step 3: Save changes in the accordion
            await self.human_delay(1, 3, wait_for_network=False)  # Brief pause before saving

            success = await self.click_save_changes_button("rooms to sell accordion")
            if not success:
                logger.error("Failed to save rooms to sell changes")
                return False

            logger.info(f"Successfully set rooms to sell to: {num_rooms}")
            return True

        except Exception as e:
            logger.error(f"Error setting rooms to sell: {e}")
            return False

    async def set_rate_plan_and_price(self, price: str) -> bool:
        """
        Select the last rate plan from dropdown and set the price

        Args:
            price: Price to set

        Returns:
            bool: True if rate plan and price set successfully
        """
        try:
            logger.info(f"Setting rate plan and price: {price}")

            # Step 1: Find and click the "Prices" button to open accordion
            prices_button = None
            button_selectors = [
                'button:has-text("Prices")',
                'button:text("Prices")',
                '[role="button"]:has-text("Prices")',
                'button[aria-expanded="false"]:has-text("Prices")'
            ]

            for selector in button_selectors:
                try:
                    prices_button = await self.page.query_selector(selector)
                    if prices_button and await prices_button.is_visible():
                        break
                except:
                    continue

            if not prices_button:
                logger.error("Could not find 'Prices' button")
                return False

            logger.info("Clicking 'Prices' button to open accordion")
            await prices_button.click()
            await self.human_delay(2, 4, wait_for_network=False)  # Wait for accordion to open

            # Step 2: Find the rate plan dropdown and select the last option
            rate_plan_select = await self.page.query_selector('select#price-select-0')
            if not rate_plan_select:
                # Try alternative selectors for the rate plan dropdown
                rate_plan_selectors = [
                    'select[id*="price-select"]',
                    'select.bui-form__control:has(option[value*="|"])',
                    'select:has(option[value*="|"])'
                ]

                for selector in rate_plan_selectors:
                    try:
                        rate_plan_select = await self.page.query_selector(selector)
                        if rate_plan_select:
                            break
                    except:
                        continue

            if not rate_plan_select:
                logger.error("Could not find rate plan select dropdown")
                return False

            # Get all options and find the last one (highest guest capacity)
            options = await rate_plan_select.query_selector_all('option[value]:not([disabled]):not([value=""])')
            if not options:
                logger.error("No valid rate plan options found")
                return False

            # Select the last option (usually has the maximum guests)
            last_option = options[-1]
            option_value = await last_option.get_attribute('value')
            option_text = await last_option.inner_text()

            logger.info(f"Selecting rate plan: {option_text}")
            await rate_plan_select.select_option(value=option_value)
            await self.human_delay(1, 2, wait_for_network=False)

            # Step 3: Find and set the price input
            price_input = await self.page.query_selector('input#price-input-0')
            if not price_input:
                # Try alternative selectors for price input
                price_input_selectors = [
                    'input[id*="price-input"]',
                    'input[name*="price"]',
                    'input[aria-describedby*="price"]',
                    'input.bui-form__control[type="text"]'
                ]

                for selector in price_input_selectors:
                    try:
                        price_input = await self.page.query_selector(selector)
                        if price_input and await price_input.is_visible():
                            break
                    except:
                        continue

            if not price_input:
                logger.error("Could not find price input field")
                return False

            # Clear existing value and input new price
            await price_input.click()
            await self.page.keyboard.press('Control+a')  # Select all
            await self.page.keyboard.press('Delete')     # Delete selected text
            await self.human_delay(0.3, 0.8, wait_for_network=False)

            await price_input.type(str(price), delay=random.randint(30, 70))
            logger.info(f"Set price to: {price}")

            # Step 4: Save changes
            await self.human_delay(1, 3, wait_for_network=False)  # Brief pause before saving

            success = await self.click_save_changes_button("prices accordion")
            if not success:
                logger.error("Failed to save rate plan and price changes")
                return False

            logger.info(f"Successfully set rate plan to: {option_text} and price to: {price}")
            return True

        except Exception as e:
            logger.error(f"Error setting rate plan and price: {e}")
            return False

    async def set_room_status_open(self) -> bool:
        """
        Set room status to "Open room" in the modal

        Returns:
            bool: True if room status set successfully
        """
        try:
            logger.info("Setting room status to open")

            # Step 1: Find and click the "Room status" button to open accordion
            room_status_button = None
            button_selectors = [
                'button:has-text("Room status")',
                'button:text("Room status")',
                '[role="button"]:has-text("Room status")',
                'button[aria-expanded="false"]:has-text("Room status")'
            ]

            for selector in button_selectors:
                try:
                    room_status_button = await self.page.query_selector(selector)
                    if room_status_button and await room_status_button.is_visible():
                        break
                except:
                    continue

            if not room_status_button:
                logger.error("Could not find 'Room status' button")
                return False

            logger.info("Clicking 'Room status' button to open accordion")
            await room_status_button.click()
            await self.human_delay(2, 4, wait_for_network=False)  # Wait for accordion to open

            # Step 2: Find and click the "Open room" option
            # Try clicking on the span text first as suggested
            open_room_span = await self.page.query_selector('span:has-text("Open room")')
            if open_room_span:
                logger.info("Clicking on 'Open room' span")
                await open_room_span.click()
                await self.human_delay(2, 4, wait_for_network=False)  # Wait for selection to register
            else:
                # Fallback to radio button if span not found
                open_room_radio = await self.page.query_selector('input#single-room-status-input-open')
                if not open_room_radio:
                    # Try alternative selectors
                    radio_selectors = [
                        'input[type="radio"][name="rate"][value="true"]',
                        'input[id*="room-status"][value="true"]',
                        'label:has-text("Open room") input[type="radio"]'
                    ]

                    for selector in radio_selectors:
                        try:
                            open_room_radio = await self.page.query_selector(selector)
                            if open_room_radio:
                                break
                        except:
                            continue

                if not open_room_radio:
                    logger.error("Could not find 'Open room' radio button or span")
                    return False

                logger.info("Clicking 'Open room' radio button")
                await open_room_radio.click()
                await self.human_delay(2, 4, wait_for_network=False)  # Wait for selection to register

            # Step 3: Wait for save button to become enabled and then click it
            logger.info("Waiting for save button to become enabled...")

            # Wait a bit more for the form to update after radio selection
            await self.human_delay(1, 2, wait_for_network=False)

            success = await self.click_save_changes_button("room status accordion")
            if not success:
                logger.error("Failed to save room status changes")
                return False

            logger.info("Successfully set room status to: Open room")
            return True

        except Exception as e:
            logger.error(f"Error setting room status to open: {e}")
            return False

    async def close_edit_modal(self) -> bool:
        """
        Close the bulk edit modal without saving

        Returns:
            bool: True if modal closed successfully
        """
        try:
            logger.info("Closing bulk edit modal")

            # Close the modal using the close button
            close_button_selector = 'button.av-general-modal__close'

            try:
                await self.page.wait_for_selector(close_button_selector, timeout=5000)
                close_button = await self.page.query_selector(close_button_selector)

                if close_button:
                    is_visible = await close_button.is_visible()
                    if is_visible:
                        logger.info("Clicking modal close button")
                        await close_button.click()

                        # Wait for modal to close
                        await asyncio.sleep(2)

                        # Verify modal is closed by checking if close button is no longer visible
                        try:
                            await self.page.wait_for_selector(close_button_selector, state='hidden', timeout=3000)
                            logger.info("Modal successfully closed")
                            return True
                        except:
                            logger.warning("Modal close button still visible, but continuing")
                            return True
                    else:
                        logger.error("Close button found but not visible")
                        return False
                else:
                    logger.error("Close button not found")
                    return False

            except Exception as e:
                logger.error(f"Failed to find or click close button: {e}")

                # Fallback: try to press Escape key to close modal
                logger.info("Trying to close modal with Escape key as fallback")
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(1)
                return True

        except Exception as e:
            logger.error(f"Error closing modal: {e}")
            return False

    async def select_date_range(self, start_date: str, end_date: str) -> bool:
        """
        Select a date range in the calendar (legacy method - use process_all_rooms instead)
        """
        logger.warning("Legacy method called - use process_all_rooms() instead")
        return False

    async def update_room_rate(self, room_type: str, new_rate: float, date_range: Tuple[str, str]) -> bool:
        """
        Update rate for a specific room type and date range (legacy method - use process_all_rooms instead)
        """
        logger.warning("Legacy method called - use process_all_rooms() instead")
        return False
