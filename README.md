Searcharr Plus - Your Smart Media Manager Bot
Telegram Bot Inspired by Searchrr by toddrob99, Searchrr Plus is an enhanced Telegram bot for Radarr and Sonarr with a key feature: Before adding media, it checks availability on your subscribed streaming services to prevent unnecessary downloads. It's easily deployed with Docker and features a guided setup. Searcharr Plus allows admins to effortlessly add new movies and shows, while friends can check library status and streaming availability without needing direct access to your services.

✨ Features
Admin & Friend Roles: A secure, two-tier access system. Admins have full control, while friends can be granted read-only access with unique, revokable codes.

Intelligent Media Workflow:

Plex Integration: Before anything else, the bot checks if a movie or show is already available in your Plex library.

Overseerr Integration: If not in Plex, it checks for pending requests in Overseerr to avoid duplicates.

TMDB Streaming Info: For new media, it checks availability on popular streaming platforms based on your region and subscribed services, helping you save on unnecessary downloads.

Interactive Interface: All search commands (/movie, /show, /status) provide a rich, interactive carousel with posters, summaries, and action buttons for easy navigation and selection.

Friend Management: Admins can easily generate and manage access codes for friends and family directly from the bot.

Guided & Persistent Setup:

An easy-to-use /setup command within Telegram handles all configuration for URLs and API keys.

All settings are saved in a config.json file, surviving bot restarts and container recreations.

Docker-First Deployment: Optimized for easy, one-command deployment using Docker and Docker Compose, perfect for home servers like a Raspberry Pi.

Flexible & Multi-Lingual: Use /skip during setup to configure only the services you need. The interface is available in English, Portuguese, and Spanish and can be changed anytime with /language.

📋 Prerequisites
Docker & Docker Compose: The recommended way to run the bot.

Telegram Bot Token: Get one from @BotFather on Telegram.

TMDB API Key: A free API key from The Movie Database is required for searching and checking streaming providers.

Running Services: Instances of Radarr, Sonarr, Plex, and/or Overseerr that are accessible from where the bot is running.

🚀 Installation & Setup
Clone the Repository

git clone https://github.com/your-username/searchrr-plus.git
cd searchrr-plus

Create the Environment File
The bot requires a Token, an Admin Username, and a Password to start. Copy the example file:

cp .env.example .env

Open the .env file (nano .env) and set your credentials:

# Credentials for the bot's admin user
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u-abcDEF123
BOT_USER=admin
BOT_PASSWORD=your_secure_password

Build and Run with Docker
From the project's root directory, run:

docker-compose up -d --build

This will build the Docker image and start the container in detached mode. To check the logs:

docker-compose logs -f

First-Time Setup via Telegram

Login: Start a chat with your bot and use the /login command with the credentials from your .env file.

Configure: Use the /setup command. The bot will guide you through configuring the URLs and API keys for each service.

Skip (Optional): You can use /skip at any prompt to bypass the configuration for a specific service (e.g., skip the Radarr section if you only use Sonarr).

🤖 Bot Commands
Admin Commands
/login: Authenticate as the admin.

/setup: Start the guided setup to configure services.

/movie <name>: Searches Radarr for a movie and provides an option to add it.

/show <name>: Searches Sonarr for a series and provides an option to add it.

/status <movie|show> <name>: Searches for media and provides an interface to check if it's in Plex or requested on Overseerr.

/friends: Manage friend access (add, remove, list).

/language: Change the bot's display language.

/logout: Log out from the bot.

/help: Shows the list of admin commands.

Friend Commands
/auth <code>: Authenticate using a friend code.

/movie <name>: Searches for a movie and checks its availability on your subscribed streaming services.

/show <name>: Searches for a series and checks its availability on your subscribed streaming services.

/status <movie|show> <name>: Checks if a media item is already on the admin's Plex or has been requested.

/logout: End your session.

/help: Shows the list of available commands.

📁 Project Structure
.
├── config/             # (Auto-generated) Stores the persistent config.json file
├── logs/               # (Auto-generated) Stores log files
├── .env                # (You create) Your private Telegram Bot Token and admin credentials
├── .env.example        # Example environment file
├── bot.py              # The main Python script for the bot
├── docker-compose.yml  # Docker Compose file for easy deployment
├── Dockerfile          # Instructions to build the Docker image
└── requirements.txt    # Python dependencies

![image](https://github.com/user-attachments/assets/676616a9-a5fc-4585-8f51-639088a37416)
![image](https://github.com/user-attachments/assets/3d98a191-4804-47a2-9714-c9b72a03e7b2)

