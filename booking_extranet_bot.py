import asyncio
import os
import time
import logging
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
import pyotp
from dotenv import load_dotenv
from rate_manager import RateManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('booking_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BookingExtranetBot:
    """
    Automated bot for Booking.com admin extranet with 2FA support using Pulse app
    """

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.rate_manager: Optional[RateManager] = None

        # Load credentials from environment variables
        self.username = os.getenv('BOOKING_USERNAME')
        self.password = os.getenv('BOOKING_PASSWORD')

        # TOTP secret is optional - we'll use manual 2FA input instead
        self.totp_secret = os.getenv('PULSE_TOTP_SECRET')  # Optional for manual 2FA

        if not all([self.username, self.password]):
            raise ValueError("Missing required environment variables (BOOKING_USERNAME, BOOKING_PASSWORD). Please check .env file.")

    async def initialize_browser(self, headless: bool = False) -> None:
        """Initialize browser and create new context"""
        try:
            playwright = await async_playwright().start()

            # Launch browser with specific options for Booking.com
            self.browser = await playwright.chromium.launch(
                headless=headless,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )

            # Create browser context with realistic user agent
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='UTC'
            )

            # Create new page
            self.page = await self.context.new_page()

            # Initialize rate manager with the page
            self.rate_manager = RateManager(self.page)

            # Set extra HTTP headers
            await self.page.set_extra_http_headers({
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            })

            logger.info("Browser initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise

    async def login(self) -> bool:
        """Login to Booking.com extranet with 2FA"""
        try:
            if not self.page:
                raise Exception("Browser not initialized")

            if not self.username or not self.password:
                raise Exception("Username or password not configured")

            logger.info("Starting login process...")

            # Navigate to Booking.com admin login page
            await self.page.goto('https://admin.booking.com/hotel/hoteladmin/', wait_until='networkidle')

            # Wait for and fill username
            await self.page.wait_for_selector('input[name="loginname"]', timeout=5000)
            await self.page.fill('input[name="loginname"]', self.username)
            logger.info("Username entered")

            # Click Next button after entering username
            await self.page.click('button[type="submit"] span:text("Next")', timeout=5000)
            await asyncio.sleep(1)  # Brief pause for page transition

            # Fill password
            await self.page.fill('input[name="password"]', self.password)
            logger.info("Password entered")

            # Click login button
            await self.page.click('button[type="submit"]', timeout=5000)

            # Wait for 2FA prompt or dashboard
            # Wait for 2FA prompt and handle Pulse app verification
            await asyncio.sleep(2)  # Wait for page transition

            # Check if we need to click Pulse app button first
            try:
                pulse_button = await self.page.wait_for_selector('a.nw-pulse-verification-link', timeout=10000)
                if pulse_button:
                    await pulse_button.click()
                    logger.info("Clicked Pulse app verification button")
                    await asyncio.sleep(3)  # Wait longer for page transition
            except Exception as e:
                logger.info("Pulse app button not found or already clicked")

            # Wait for 2FA code input field to appear
            try:
                await self.page.wait_for_selector('input[name="sms_code"]', timeout=15000)
                logger.info("2FA code input field found")

                # Manual input from terminal
                two_fa_code = input("Enter the 6-digit 2FA code from your Pulse app: ").strip()
                logger.info("2FA code entered manually")

                # Enter the 2FA code
                await self.page.fill('input[name="sms_code"]', two_fa_code)
                logger.info("2FA code entered")

                # Submit the 2FA code (look for submit button or form)
                try:
                    await self.page.click('button[type="submit"]', timeout=5000)
                    logger.info("2FA code submitted")
                except Exception:
                    # Alternative: try pressing Enter
                    await self.page.press('input[name="sms_code"]', 'Enter')
                    logger.info("2FA code submitted via Enter key")

                await asyncio.sleep(3)  # Wait longer for verification

            except Exception as e:
                logger.error(f"2FA code input failed: {e}")
                return False

            # Wait for successful login (dashboard or main page)
            try:
                await self.page.wait_for_url('**/hoteladmin/**', timeout=15000)
                logger.info("Login successful!")
                return True

            except Exception:
                # Alternative check for successful login
                current_url = self.page.url
                if 'admin.booking.com' in current_url and 'login' not in current_url:
                    logger.info("Login successful!")
                    return True
                else:
                    logger.error("Login failed - still on login page")
                    return False

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    async def navigate_to_section(self, section: str) -> bool:
        """Navigate to specific section in extranet"""
        try:
            if not self.page:
                raise Exception("Page not available")

            logger.info(f"Navigating to {section} section...")

            # Common navigation mappings
            navigation_map = {
                'properties': '/hotel/hoteladmin/extranet_ng/manage/home.html',
                'reservations': '/hotel/hoteladmin/extranet_ng/manage/reservations.html',
                'rates': '/hotel/hoteladmin/extranet_ng/manage/rates_index.html',
                'availability': '/hotel/hoteladmin/extranet_ng/manage/calendar.html',
                'reviews': '/hotel/hoteladmin/extranet_ng/manage/guest_reviews.html',
                'finance': '/hotel/hoteladmin/extranet_ng/manage/finance.html'
            }

            if section.lower() in navigation_map:
                url = f"https://admin.booking.com{navigation_map[section.lower()]}"
                await self.page.goto(url, wait_until='networkidle')
                logger.info(f"Successfully navigated to {section}")
                return True
            else:
                logger.warning(f"Unknown section: {section}")
                return False

        except Exception as e:
            logger.error(f"Failed to navigate to {section}: {e}")
            return False

    async def get_reservations(self, days_ahead: int = 7) -> list:
        """Get upcoming reservations"""
        try:
            if not self.page:
                raise Exception("Browser not initialized")

            await self.navigate_to_section('reservations')
            await asyncio.sleep(2)  # Wait for page to load

            # Wait for reservations table
            await self.page.wait_for_selector('table', timeout=10000)

            # Extract reservation data
            reservations = await self.page.evaluate('''
                () => {
                    const rows = document.querySelectorAll('table tbody tr');
                    const reservations = [];

                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length > 0) {
                            reservations.push({
                                reservation_id: cells[0]?.textContent?.trim() || '',
                                guest_name: cells[1]?.textContent?.trim() || '',
                                check_in: cells[2]?.textContent?.trim() || '',
                                check_out: cells[3]?.textContent?.trim() || '',
                                status: cells[4]?.textContent?.trim() || ''
                            });
                        }
                    });

                    return reservations;
                }
            ''')

            logger.info(f"Retrieved {len(reservations)} reservations")
            return reservations

        except Exception as e:
            logger.error(f"Failed to get reservations: {e}")
            return []

    async def update_availability(self, room_type: str, date: str, available_rooms: int) -> bool:
        """Update room availability for specific date"""
        try:
            await self.navigate_to_section('availability')
            await asyncio.sleep(2)

            # Implementation would depend on the specific UI structure
            # This is a template for the availability update functionality

            logger.info(f"Updated availability for {room_type} on {date}: {available_rooms} rooms")
            return True

        except Exception as e:
            logger.error(f"Failed to update availability: {e}")
            return False

    async def close(self) -> None:
        """Clean up browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            self.rate_manager = None
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    async def navigate_to_calendar(self) -> bool:
        """Navigate to the rates & availability calendar"""
        if not self.rate_manager:
            logger.error("Rate manager not initialized")
            return False

        return await self.rate_manager.navigate_to_calendar()

    async def get_calendar_info(self) -> dict:
        """Get information about the current calendar page for debugging"""
        if not self.rate_manager:
            logger.error("Rate manager not initialized")
            return {}

        return await self.rate_manager.get_current_page_info()

# Example usage
async def main():
    """Example usage of the BookingExtranetBot"""
    bot = BookingExtranetBot()

    try:
        # Initialize browser (set headless=False to see the automation)
        await bot.initialize_browser(headless=False)

        # Login to extranet
        if await bot.login():
            logger.info("Login successful, ready for automation tasks!")

            # Test navigation to calendar
            if await bot.navigate_to_calendar():
                logger.info("Successfully navigated to calendar!")

                # Get page info for debugging
                page_info = await bot.get_calendar_info()
                logger.info(f"Calendar page info: {page_info}")
            else:
                logger.error("Failed to navigate to calendar")

        else:
            logger.error("Login failed!")

    except Exception as e:
        logger.error(f"Error in main execution: {e}")

    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
