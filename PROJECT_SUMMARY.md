# 🤖 Booking.com Extranet Automation Bot

## 🎯 Project Overview

This Python automation bot helps you automate tasks in the Booking.com admin extranet using Playwright for web automation and Pulse app for 2FA authentication.

## ✨ Key Features

- **🔐 Secure Login**: Automated login with 2FA support using Pulse app
- **🚀 Browser Automation**: Uses Playwright for reliable web automation
- **📊 Data Extraction**: Get reservations, reviews, and property data
- **⚙️ Task Automation**: Configurable automation workflows
- **📝 Comprehensive Logging**: Detailed logs for monitoring and debugging
- **🛡️ Security First**: Environment variables for credentials, no hardcoded secrets

## 📁 Project Structure

```
Booking.com bot/
├── .env                      # Your credentials (DO NOT COMMIT)
├── .env.example             # Template for environment variables
├── .gitignore               # Git ignore file
├── README.md                # Main documentation
├── requirements.txt         # Python dependencies
├── booking_extranet_bot.py  # Main bot class
├── automation_tasks.py      # Predefined automation tasks
├── setup_2fa.py            # 2FA setup helper
├── test_bot.py             # Test script
├── setup.py                # Quick setup script
└── .github/
    └── copilot-instructions.md # GitHub Copilot configuration
```

## 🚀 Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Run Setup**:
   ```bash
   python setup.py
   ```

3. **Configure 2FA**:
   ```bash
   python setup_2fa.py
   ```

4. **Edit .env file** with your credentials

5. **Test Setup**:
   ```bash
   python test_bot.py
   ```

6. **Run the Bot**:
   ```bash
   python booking_extranet_bot.py
   ```

## 🔧 Configuration

Edit `.env` file:
```
BOOKING_USERNAME=your_username
BOOKING_PASSWORD=your_password
PULSE_TOTP_SECRET=your_base32_secret_from_pulse
```

## 🎮 Usage Examples

### Basic Usage
```python
import asyncio
from booking_extranet_bot import BookingExtranetBot

async def main():
    bot = BookingExtranetBot()

    await bot.initialize_browser(headless=False)

    if await bot.login():
        # Get reservations
        reservations = await bot.get_reservations()
        print(f"Found {len(reservations)} reservations")

        # Navigate to different sections
        await bot.navigate_to_section('rates')
        await bot.navigate_to_section('reviews')

    await bot.close()

asyncio.run(main())
```

### Automation Tasks
```bash
python automation_tasks.py  # Run predefined tasks
```

## 🛠️ Available Methods

- `initialize_browser(headless=False)` - Start browser session
- `login()` - Login with credentials and 2FA
- `generate_2fa_code()` - Generate TOTP code from Pulse
- `navigate_to_section(section)` - Navigate to extranet sections
- `get_reservations(days_ahead=7)` - Get upcoming reservations
- `update_availability(room_type, date, rooms)` - Update room availability
- `close()` - Clean up browser resources

## 📍 Supported Sections

- `properties` - Property management
- `reservations` - Reservation management
- `rates` - Rate and pricing management
- `availability` - Room availability calendar
- `reviews` - Guest reviews
- `finance` - Financial reports

## 🔒 Security & Compliance

- ✅ Credentials stored in environment variables
- ✅ TOTP secrets securely handled
- ✅ No sensitive data in code
- ✅ Respects website terms of service
- ⚠️ Use responsibly and within rate limits

## 🐛 Troubleshooting

### Login Issues
- Verify credentials in .env file
- Check 2FA secret is correct
- Ensure device time is synchronized

### Browser Issues
- Try running with `headless=False` to see what's happening
- Check system resources and Chrome installation
- Review logs in `booking_bot.log`

### 2FA Problems
- Regenerate TOTP secret if needed
- Verify Pulse app is synchronized
- Check secret format (Base32)

## 📝 Development

### Adding New Features
1. Extend the `BookingExtranetBot` class
2. Add new methods for specific tasks
3. Update automation_tasks.py with new workflows
4. Test thoroughly before production use

### Contributing
- Follow PEP 8 style guidelines
- Add comprehensive error handling
- Include logging for debugging
- Write tests for new features

## ⚖️ Legal & Ethical Use

This tool is designed for legitimate property management purposes only:
- ✅ Automate routine administrative tasks
- ✅ Monitor property performance
- ✅ Manage reservations efficiently
- ❌ Do not violate Booking.com Terms of Service
- ❌ Do not exceed reasonable usage limits
- ❌ Do not interfere with platform operations

## 📞 Support

For issues or questions:
1. Check troubleshooting section
2. Review log files for errors
3. Verify environment configuration
4. Ensure all dependencies are installed

---

**Made with ❤️ for property managers who want to automate their Booking.com workflows**
