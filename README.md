Searchrr Plus - Telegram Bot
Inspired by Searchrr by toddrob99, Searchrr Plus is an enhanced Telegram bot for Radarr and Sonarr with a key feature: Overseerr integration. Before adding media, it checks availability on your subscribed streaming services to prevent unnecessary downloads. It's easily deployed with Docker and features a guided setup.

🌟 What's New
Optional Plex Integration: The bot can now check your Plex libraries directly! Before checking any other service, it will verify if the movie or show is already available on one of your configured Plex servers, making it the ultimate source of truth for your library.

Friend Mode: Share your bot securely! As an admin, you can now generate unique access codes for friends. Friends can use the bot to check what's available in your library but cannot add new media or change any settings.

✨ Features
Radarr & Sonarr Integration: Search and add movies (Radarr) and series (Sonarr).

TMDB Integration: Checks if media is already available on your server or on your subscribed streaming platforms before adding.

*Alternative:
Overseerr Integration: Checks if media is already available on your server or on your subscribed streaming platforms before adding.*

Interactive Search: Displays search results as a navigable carousel with posters, summaries, and TMDB links.

Guided Setup: Easy-to-use /setup command within Telegram to configure all API keys and URLs. No more manual .env file editing for complex fields.

Flexible Configuration: Use /skip during setup to run the bot for movies only, series only, or both.

Multi-Language Support: Interface available in English (default), Portuguese, and Spanish. Change it anytime with the /language command.

Dockerized: Simple, one-command deployment using Docker and Docker Compose, perfect for home servers like a Raspberry Pi.

Persistent Configuration: All settings are saved in a JSON file, surviving bot restarts and container recreations.

📋 Prerequisites
Docker: Install Docker

Docker Compose: Install Docker Compose

Telegram Bot Token: Get one from @BotFather on Telegram.

Radarr, Sonarr, Overseerr: You should have running instances of these services, accessible from where you are running the bot.

🚀 Installation & Setup
Follow these steps to get your bot up and running.

1. Clone the Repository
Clone this repository to your local machine or server (e.g., your Raspberry Pi).

git clone [https://github.com/your-username/searcharr-plus.git](https://github.com/your-username/searcharr-plus.git)
cd searcharr-plus

2. Create the Environment File
The bot now requires a Token, a Username, and a Password to start.

Make a copy of the example environment file:

cp .env.example .env

Open the .env file (nano .env) and set your credentials:

# Credentials for the bot
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u-abcDEF123
BOT_USER=admin
BOT_PASSWORD=your_secure_password

3. Build and Run the Docker Container
With Docker and Docker Compose installed, run the following command from the project's root directory:

docker-compose up -d --build

This command will:

Build the Docker image for the bot.

Start the container in detached mode (-d).

Automatically restart the container if it stops or if the server reboots.

To check if the bot started correctly, you can view its logs:

docker-compose logs -f

Press Ctrl+C to exit the logs.

4. First-Time Setup & Login via Telegram
Start a Chat: Open Telegram and start a chat with the bot you created.

Login: Send the /login command and provide the username and password you set in the .env file.

Initiate Setup: Once logged in, send the /setup command.

Follow the Guide: The bot will ask for each required piece of information.

Skip Sections (Optional):

If you only want to use the bot for series, send /skip when it asks for the Radarr URL.

If you only want to use the bot for movies, send /skip when it asks for the Sonarr URL.

Complete: Once done, the bot will save the configuration and be fully operational.

🤖 Usage
/start: Shows a welcome message.

/login: Starts the admin login process.

/auth <code>: Allows a friend to log in with their unique access code.

/logout: Logs out of the current session.

/help: Displays a list of all available commands.

/friends: Manage friend access codes (admin only).

/movie <name>: Searches for a movie.

/show <name>: Searches for a TV series.

/language: Opens a menu to change the language.

/streaming: Lists recognized streaming service codes.

/setup: Starts the guided configuration process.

📁 Project Structure
.
├── config/             # (Auto-generated) Stores the persistent config.json file
├── logs/               # (Auto-generated) Stores log files
├── .env                # (You create) Your private Telegram Bot Token
├── .env.example        # Example environment file
├── bot.py              # The main Python script for the bot
├── docker-compose.yml  # Docker Compose file for easy deployment
├── Dockerfile          # Instructions to build the Docker image
└── requirements.txt    # Python dependencies

🤝 Contributing
Contributions are welcome! If you have ideas for new features, find a bug, or want to improve the code, feel free to:

Fork the repository.

Create a new branch (git checkout -b feature/my-new-feature).

Make your changes.

Commit your changes (git commit -am 'Add some feature').

Push to the branch (git push origin feature/my-new-feature).

Create a new Pull Request.
![image](https://github.com/user-attachments/assets/676616a9-a5fc-4585-8f51-639088a37416)
![image](https://github.com/user-attachments/assets/3d98a191-4804-47a2-9714-c9b72a03e7b2)

