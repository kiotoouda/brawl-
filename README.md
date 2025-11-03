# Brawl Stars Tournament Bot

A Telegram bot for managing Brawl Stars tournaments with team registration, bracket generation, and match management.

## Features

- **Team Registration**: Teams can register with name, leader username, and roster photos
- **Tournament Management**: Admins can create/delete tournaments
- **Bracket System**: Automatic bracket generation and progression
- **Match Management**: Admins can report winners via buttons
- **Roster Sharing**: Players can view other teams' rosters

## Setup

1. **Create Bot**: Talk to @BotFather on Telegram to create a bot and get token
2. **Deploy to Render**:
   - Fork this repository
   - Connect your GitHub to Render
   - Create new Web Service
   - Set environment variables:
     - `TELEGRAM_BOT_TOKEN`: Your bot token from BotFather
     - `WEBHOOK_URL`: Your Render app URL (e.g., https://your-app.onrender.com)

## Admin Commands

- `/create <name> <max_teams> <description>` - Create tournament
- `/generate_bracket <tournament_id>` - Generate bracket

## Environment Variables

- `TELEGRAM_BOT_TOKEN`: Bot token (required)
- `WEBHOOK_URL`: Your app URL (required for webhook)
- `ADMINS`: Comma-separated admin user IDs (optional)
