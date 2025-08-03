# Copilot Instructions

<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

This is a Python automation project for Booking.com extranet with the following specifications:

## Project Context
- **Purpose**: Automate processes in Booking.com admin extranet
- **Technology**: Python with Playwright for web automation
- **2FA Method**: Pulse app integration for two-factor authentication
- **Target Platform**: Booking.com Partner/Property Extranet

## Key Components
- Web automation using Playwright
- 2FA handling with TOTP (Time-based One-Time Password)
- Configuration management for credentials
- Error handling and logging
- Modular structure for different automation tasks

## Code Style Guidelines
- Use async/await patterns for Playwright operations
- Implement proper error handling and timeouts
- Add comprehensive logging for debugging
- Use type hints for better code clarity
- Follow PEP 8 style guidelines
- Create reusable functions for common operations

## Security Considerations
- Store sensitive data (credentials, secrets) in environment variables
- Never commit credentials to version control
- Use secure methods for 2FA token generation
- Implement session management and cleanup
