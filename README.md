# Booking.com Extranet Automation Bot

A Python automation bot for Booking.com admin extranet with 2FA support using Pulse app.

## Features

- **Automated Login**: Secure login with username/password and 2FA
- **Manual 2FA Support**: Prompts you to enter 2FA codes from your Pulse app
- **Optional Auto-2FA**: Can auto-generate codes if you provide TOTP secret
- **Extranet Navigation**: Navigate between different sections (reservations, rates, availability, etc.)
- **Data Extraction**: Get reservations, reviews, and other property data
- **Task Automation**: Configurable automation tasks and scheduled operations
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

## Prerequisites

- Python 3.8 or higher
- Booking.com Partner/Property account with admin access
- Pulse app installed on your mobile device for 2FA
- Chrome/Chromium browser (automatically handled by Playwright)

## Installation

1. **Clone or download the project files**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**:
   ```bash
   playwright install chromium
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` file with your credentials:
   ```
   BOOKING_USERNAME=your_booking_username
   BOOKING_PASSWORD=your_booking_password
   # PULSE_TOTP_SECRET=your_base32_secret  # Optional for auto-2FA
   ```

## 2FA Authentication Options

### Option 1: Manual 2FA (Recommended)
The bot will prompt you to enter the 2FA code from your Pulse app when needed:
- No additional setup required
- Most secure approach
- You remain in control of 2FA codes

### Option 2: Automatic 2FA (Optional)
Set up TOTP secret for automatic code generation:

1. **Generate TOTP secret**:
   ```bash
   pip install qrcode[pil]  # Install QR code dependencies
   python setup_2fa.py
   ```

2. **Configure Pulse app**:
   - Open Pulse app on your mobile device
   - Add new TOTP entry
   - Scan the QR code or manually enter the secret
   - Set account name as "Booking.com Extranet"

3. **Update .env file**:
   - Copy the generated secret to `PULSE_TOTP_SECRET` in your `.env` file

## Usage

### Basic Usage

```python
import asyncio
from booking_extranet_bot import BookingExtranetBot

async def main():
    bot = BookingExtranetBot()

    try:
        # Initialize browser
        await bot.initialize_browser(headless=False)

        # Login with 2FA (you'll be prompted for 2FA code)
        if await bot.login():
            print("Login successful!")

            # Get reservations
            reservations = await bot.get_reservations()
            for reservation in reservations:
                print(f"Reservation: {reservation}")

            # Navigate to different sections
            await bot.navigate_to_section('rates')
            await bot.navigate_to_section('reviews')

    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Manual 2FA Workflow

When you run the bot, you'll see:
```
🔐 2FA Required!
Please open your Pulse app and get the current 2FA code.
Enter the 6-digit 2FA code from Pulse app: ######
```

Simply enter the 6-digit code from your Pulse app and the bot will continue automatically.

    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Running Automation Tasks

```bash
# Run daily checklist
python automation_tasks.py

# Or import and use specific tasks
```

### Available Methods

- `initialize_browser(headless=False)`: Start browser session
- `login()`: Login with credentials and 2FA
- `navigate_to_section(section)`: Navigate to extranet sections
- `get_reservations(days_ahead=7)`: Get upcoming reservations
- `update_availability(room_type, date, rooms)`: Update room availability
- `close()`: Clean up browser resources

### Supported Sections

- `properties`: Property management
- `reservations`: Reservation management
- `rates`: Rate and pricing management
- `availability`: Room availability calendar
- `reviews`: Guest reviews
- `finance`: Financial reports

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BOOKING_USERNAME` | Booking.com username | Yes |
| `BOOKING_PASSWORD` | Booking.com password | Yes |
| `PULSE_TOTP_SECRET` | Base32 TOTP secret from Pulse | Yes |
| `HTTP_PROXY` | HTTP proxy (if needed) | No |
| `HTTPS_PROXY` | HTTPS proxy (if needed) | No |

### Browser Options

You can customize browser behavior by modifying the `initialize_browser()` method:

- `headless=True`: Run browser in background
- Custom user agents
- Proxy settings
- Window size and viewport

## Security Notes

- Never commit your `.env` file to version control
- Use environment variables for all sensitive data
- The TOTP secret should be kept secure and not shared
- Consider using encrypted storage for production deployments

## Troubleshooting

### Common Issues

1. **Login fails**:
   - Check username/password
   - Verify 2FA secret is correct
   - Ensure Pulse app time is synchronized

2. **Browser crashes**:
   - Try running with `headless=False` to see what's happening
   - Check Chrome/Chromium installation
   - Verify sufficient system resources

3. **2FA code invalid**:
   - Ensure device time is synchronized
   - Regenerate TOTP secret if needed
   - Check secret is correctly copied to .env

4. **Navigation issues**:
   - Booking.com may update their interface
   - Check browser console for errors
   - Update selectors if needed

### Logging

All operations are logged to both console and `booking_bot.log` file. Check the logs for detailed error information.

## Extending the Bot

You can extend the bot by:

1. **Adding new automation tasks** in `automation_tasks.py`
2. **Creating new navigation methods** for additional extranet sections
3. **Adding data extraction methods** for specific information
4. **Implementing scheduling** with cron jobs or task schedulers

## Legal and Compliance

- Ensure compliance with Booking.com's Terms of Service
- Use automation responsibly and within rate limits
- This tool is for legitimate property management purposes only
- Always respect website terms of use and robots.txt

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review log files for error details
3. Ensure all dependencies are properly installed
4. Verify environment configuration

## Version History

- **v1.0.0**: Initial release with basic automation and 2FA support
