"""
Rate Management Module for Booking.com Extranet Bot

This module handles automated rate changes for different date ranges
in the Booking.com partner extranet calendar system.
"""

import asyncio
import logging
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

    # Placeholder methods for future implementation once we understand the calendar UI
    async def select_date_range(self, start_date: str, end_date: str) -> bool:
        """
        Select a date range in the calendar (to be implemented based on actual UI)
        """
        logger.info(f"Date range selection not yet implemented: {start_date} to {end_date}")
        return False

    async def update_room_rate(self, room_type: str, new_rate: float, date_range: Tuple[str, str]) -> bool:
        """
        Update rate for a specific room type and date range (to be implemented based on actual UI)
        """
        logger.info(f"Rate update not yet implemented: {room_type} = {new_rate} for {date_range}")
        return False
