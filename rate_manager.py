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

            # Get room data from CSV
            room_data = self.get_room_data_by_id(room_info['id'])
            if not room_data:
                logger.error(f"No CSV data found for room ID {room_info['id']}")
                await self.close_modal_emergency()
                return False

            logger.info(f"Found {len(room_data)} pricing records for room {room_info['name']}")

            # Process each date range for this room
            for i, record in enumerate(room_data):
                logger.info(f"Processing date range {i+1}/{len(room_data)} for room {room_info['name']}")

                success = await self.process_date_range_in_modal(record)
                if not success:
                    logger.error(f"Failed to process date range for record: {record}")
                    await self.close_modal_emergency()
                    return False

                # Small delay between date range updates
                await asyncio.sleep(1)

            # Save and close modal after all date ranges are processed
            success = await self.save_and_close_modal()
            if not success:
                logger.error(f"Failed to save and close modal for room {room_info['name']}")
                await self.close_modal_emergency()
                return False

            logger.info(f"Successfully completed bulk edit for room {room_info['name']}")
            return True

        except Exception as e:
            logger.error(f"Error handling bulk edit modal: {e}")
            await self.close_modal_emergency()
            return False

    async def close_modal_emergency(self) -> None:
        """
        Emergency modal close function using multiple methods
        """
        try:
            logger.warning("Attempting emergency modal close")

            # Try close button first
            try:
                close_button = await self.page.query_selector('button.av-general-modal__close')
                if close_button and await close_button.is_visible():
                    await close_button.click()
                    await asyncio.sleep(1)
                    return
            except:
                pass

            # Try escape key
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(1)

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

            # Ensure dates are from today onwards
            today = datetime.now()
            if start_date < today:
                start_date = today
                logger.info(f"Adjusted start date to today: {start_date.strftime('%Y-%m-%d')}")

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
            await start_date_input.type(start_date_str, delay=50)
            await asyncio.sleep(0.5)
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
            await asyncio.sleep(0.5)

            # Type the end date
            await end_date_input.type(end_date_str, delay=50)
            await asyncio.sleep(0.5)
            logger.info(f"End date set to: {end_date_str}")

            # Optional: Press Tab or click elsewhere to trigger any date validation
            await end_date_input.press('Tab')
            await asyncio.sleep(1)
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
            await asyncio.sleep(1)  # Wait for accordion to open

            # Step 2: Find and input the number of rooms in the opened accordion
            rooms_input = await self.page.query_selector('input#single-rts-input')
            if not rooms_input:
                logger.error("Could not find rooms input field after opening accordion")
                return False

            # Clear existing value and input new number
            await rooms_input.click()
            await self.page.keyboard.press('Control+a')  # Select all
            await self.page.keyboard.press('Delete')     # Delete selected text
            await asyncio.sleep(0.2)

            await rooms_input.type(str(num_rooms), delay=50)
            logger.info(f"Input number of rooms: {num_rooms}")

            # Step 3: Find and click "Save changes" button in the accordion
            await asyncio.sleep(0.5)  # Brief pause before looking for save button

            save_button_selectors = [
                'button:has-text("Save changes")',
                'button:text("Save changes")',
                '.bui-button:has-text("Save changes")',
                '[type="submit"]:has-text("Save changes")'
            ]

            save_button = None
            for selector in save_button_selectors:
                try:
                    save_button = await self.page.query_selector(selector)
                    if save_button and await save_button.is_visible() and await save_button.is_enabled():
                        break
                except:
                    continue

            if not save_button:
                logger.error("Could not find 'Save changes' button in accordion")
                return False

            logger.info("Clicking 'Save changes' button to save rooms to sell")
            await save_button.click()
            await asyncio.sleep(1)  # Wait for save operation to complete

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
            await asyncio.sleep(1)  # Wait for accordion to open

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
            await asyncio.sleep(0.5)

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
            await asyncio.sleep(0.2)

            await price_input.type(str(price), delay=50)
            logger.info(f"Set price to: {price}")

            # Step 4: Find and click "Save changes" button
            await asyncio.sleep(0.5)  # Brief pause before looking for save button

            save_button_selectors = [
                'button:has-text("Save changes")',
                'button:text("Save changes")',
                '.bui-button:has-text("Save changes")',
                '[type="submit"]:has-text("Save changes")'
            ]

            save_button = None
            for selector in save_button_selectors:
                try:
                    save_button = await self.page.query_selector(selector)
                    if save_button and await save_button.is_visible() and await save_button.is_enabled():
                        break
                except:
                    continue

            if not save_button:
                logger.error("Could not find 'Save changes' button for prices")
                return False

            logger.info("Clicking 'Save changes' button to save rate plan and price")
            await save_button.click()
            await asyncio.sleep(1)  # Wait for save operation to complete

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
            await asyncio.sleep(1)  # Wait for accordion to open

            # Step 2: Find and click the "Open room" radio button
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
                logger.error("Could not find 'Open room' radio button")
                return False

            logger.info("Selecting 'Open room' radio button")
            await open_room_radio.click()
            await asyncio.sleep(0.5)

            # Step 3: Find and click "Save changes" button in the accordion
            save_button_selectors = [
                'button:has-text("Save changes")',
                'button:text("Save changes")',
                '.bui-button:has-text("Save changes")',
                '[type="submit"]:has-text("Save changes")'
            ]

            save_button = None
            for selector in save_button_selectors:
                try:
                    save_button = await self.page.query_selector(selector)
                    if save_button and await save_button.is_visible() and await save_button.is_enabled():
                        break
                except:
                    continue

            if not save_button:
                logger.error("Could not find 'Save changes' button for room status")
                return False

            logger.info("Clicking 'Save changes' button to save room status")
            await save_button.click()
            await asyncio.sleep(1)  # Wait for save operation to complete

            logger.info("Successfully set room status to: Open room")
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

            # First try to find and click any save/apply button if present
            save_selectors = [
                'button[type="submit"]',
                'button:has-text("Save")',
                'button:has-text("Apply")',
                'button:has-text("Update")',
                '.bui-button--primary:has-text("Save")',
                '.bui-button--primary:has-text("Apply")'
            ]

            save_button_found = False
            for selector in save_selectors:
                try:
                    save_button = await self.page.query_selector(selector)
                    if save_button:
                        # Check if button is visible and enabled
                        is_visible = await save_button.is_visible()
                        is_enabled = await save_button.is_enabled()

                        if is_visible and is_enabled:
                            logger.info(f"Found and clicking save button: {selector}")
                            await save_button.click()
                            save_button_found = True
                            await asyncio.sleep(1)  # Wait for save to process
                            break
                except Exception:
                    continue

            if save_button_found:
                logger.info("Save button clicked, waiting before closing modal")
                await asyncio.sleep(2)  # Give time for save operation

            # Now close the modal using the close button
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
