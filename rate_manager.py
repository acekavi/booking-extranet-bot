"""
Rate Management Module for Booking.com Extranet Bot

This module handles automated rate changes for different date ranges
in the Booking.com partner extranet calendar system.
"""

import asyncio
import logging
import csv
import os
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

    def load_csv_data(self) -> None:
        """
        Load pricing data from the CSV file
        """
        try:
            csv_path = os.path.join(os.path.dirname(__file__), 'public', 'seasonal_room_prices_optimized.csv')
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                self.csv_data = list(reader)
            logger.info(f"Loaded {len(self.csv_data)} pricing records from CSV")
        except Exception as e:
            logger.error(f"Failed to load CSV data: {e}")
            self.csv_data = []

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

            return start_date, end_date
        except Exception as e:
            logger.error(f"Failed to parse date range '{date_range_str}': {e}")
            return None, None

    def get_room_data_by_id(self, room_id: str) -> List[Dict]:
        """
        Get all pricing data for a specific room ID

        Args:
            room_id: Room ID to filter by

        Returns:
            List of pricing records for the room
        """
        return [record for record in self.csv_data if record['Room ID'] == room_id]

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

                    logger.info(f"Processing room: {room_info['name']} (ID: {room_info['id']})")

                    # Process this room
                    success = await self.process_single_room(room_container, room_info)
                    if not success:
                        logger.error(f"Failed to process room {room_info['name']}")
                        continue

                    logger.info(f"Successfully processed room: {room_info['name']}")

                    # Small delay between rooms to avoid overwhelming the system
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Error processing room {i+1}: {e}")
                    continue

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
            await asyncio.sleep(2)

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
            # Get room data from CSV
            room_data = self.get_room_data_by_id(room_info['id'])
            if not room_data:
                logger.error(f"No CSV data found for room ID {room_info['id']}")
                return False

            logger.info(f"Found {len(room_data)} pricing records for room {room_info['name']}")

            # Process each date range for this room
            for record in room_data:
                success = await self.process_date_range_in_modal(record)
                if not success:
                    logger.error(f"Failed to process date range for record: {record}")
                    return False

                # Small delay between date range updates
                await asyncio.sleep(1)

            # Close modal or save changes
            await self.save_and_close_modal()

            return True

        except Exception as e:
            logger.error(f"Error handling bulk edit modal: {e}")
            return False

    async def process_date_range_in_modal(self, record: Dict) -> bool:
        """
        Process a specific date range record in the bulk edit modal

        Args:
            record: CSV record with pricing information

        Returns:
            bool: True if date range processed successfully
        """
        try:
            logger.info(f"Processing date range: {record['Date Range']} with price {record['Price']}")

            # Parse date range
            start_date, end_date = self.parse_date_range(record['Date Range'])
            if not start_date or not end_date:
                logger.error(f"Failed to parse date range: {record['Date Range']}")
                return False

            # Ensure dates are from today onwards
            today = datetime.now()
            if start_date < today:
                start_date = today

            # Select date range in modal
            success = await self.select_date_range_in_modal(start_date, end_date)
            if not success:
                logger.error(f"Failed to select date range in modal")
                return False

            # Set number of rooms to sell
            success = await self.set_rooms_to_sell(record['Number of Rooms'])
            if not success:
                logger.error(f"Failed to set rooms to sell")
                return False

            # Select last rate plan and set price
            success = await self.set_rate_plan_and_price(record['Price'])
            if not success:
                logger.error(f"Failed to set rate plan and price")
                return False

            # Set room status to open
            success = await self.set_room_status_open()
            if not success:
                logger.error(f"Failed to set room status to open")
                return False

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
            # This will need to be implemented based on the actual modal UI
            # Placeholder for date selection logic
            logger.info(f"Selecting date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

            # Wait for date picker elements
            # await self.page.wait_for_selector('[data-testid="date-picker"]', timeout=5000)

            # TODO: Implement actual date selection based on modal UI
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

            # TODO: Implement based on actual modal UI
            # This might be an input field or dropdown

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
            logger.info(f"Setting price: {price}")

            # TODO: Implement based on actual modal UI
            # 1. Find rate plan dropdown
            # 2. Select the last option (with most guests)
            # 3. Set the price in the price field

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

            # TODO: Implement based on actual modal UI
            # This might be a radio button, checkbox, or dropdown

            return True

        except Exception as e:
            logger.error(f"Error setting room status to open: {e}")
            return False

    async def save_and_close_modal(self) -> bool:
        """
        Save changes and close the bulk edit modal

        Returns:
            bool: True if modal saved and closed successfully
        """
        try:
            logger.info("Saving and closing bulk edit modal")

            # TODO: Implement based on actual modal UI
            # Look for save/apply/close buttons

            return True

        except Exception as e:
            logger.error(f"Error saving and closing modal: {e}")
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
