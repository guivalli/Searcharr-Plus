# Searcharr Plus - Telegram Bot

Inspired by [Searchrr by toddrob99](https://github.com/toddrob99/searcharr), Searchrr Plus is an enhanced Telegram bot for Radarr and Sonarr with a key feature: Overseerr integration. Before adding media, it checks availability on your subscribed streaming services to prevent unnecessary downloads. It's easily deployed with Docker and features a guided setup.

## ✨ Features

* **Radarr & Sonarr Integration**: Search and add movies (Radarr) and series (Sonarr).
* **Overseerr Integration**: Checks if media is already available on your server or on your subscribed streaming platforms before adding.
* **Interactive Search**: Displays search results as a navigable carousel with posters, summaries, and TMDB links.
* **Guided Setup**: Easy-to-use `/setup` command within Telegram to configure all API keys and URLs. No more manual `.env` file editing for complex fields.
* **Flexible Configuration**: Use `/skip` during setup to run the bot for movies only, series only, or both.
* **Multi-Language Support**: Interface available in English (default), Portuguese, and Spanish. Change it anytime with the `/language` command.
* **Dockerized**: Simple, one-command deployment using Docker and Docker Compose, perfect for home servers like a Raspberry Pi.
* **Persistent Configuration**: All settings are saved in a JSON file, surviving bot restarts and container recreations.

## 📋 Prerequisites

* **Docker**: [Install Docker](https://docs.docker.com/engine/install/)
* **Docker Compose**: [Install Docker Compose](https://docs.docker.com/compose/install/)
* **Telegram Bot Token**: Get one from [@BotFather](https://t.me/BotFather) on Telegram.
* **Radarr, Sonarr, Overseerr**: You should have running instances of these services, accessible from where you are running the bot.

## 🚀 Installation & Setup

Follow these steps to get your bot up and running.

### 1. Clone the Repository

Clone this repository to your local machine or server (e.g., your Raspberry Pi).



git clone https://github.com/your-username/searcharr-plus.git
cd searcharr-plus


### 2. Create the Environment File

The bot only needs one environment variable to start: your Telegram Bot Token.

* Make a copy of the example environment file:
    ```
    cp .env.example .env
    ```
* Open the `.env` file with a text editor (like `nano .env`) and paste your bot token:
    ```
    # Only the Telegram Bot Token is needed here.
    # The rest of the configuration will be done via the /setup command in the bot.
    BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u-abcDEF123
    ```

### 3. Build and Run the Docker Container

With Docker and Docker Compose installed, run the following command from the project's root directory:



docker-compose up -d --build


This command will:

* Build the Docker image for the bot.
* Start the container in detached mode (`-d`).
* Automatically restart the container if it stops or if the server reboots.

To check if the bot started correctly, you can view its logs:



docker-compose logs -f


Press `Ctrl+C` to exit the logs.

### 4. First-Time Setup via Telegram

Your bot is now running, but it needs to be configured to connect to your services.

1.  **Start a Chat**: Open Telegram and start a chat with the bot you created.
2.  **Initiate Setup**: Send the `/setup` command.
3.  **Follow the Guide**: The bot will ask for each required piece of information one by one (URLs, API Keys, etc.). Simply reply to each message with the requested value.
4.  **Skip Sections (Optional)**:
    * If you only want to use the bot for **series**, send `/skip` when it asks for the Radarr URL.
    * If you only want to use the bot for **movies**, send `/skip` when it asks for the Sonarr URL.
5.  **Complete**: Once you've answered all the questions, the bot will save the configuration and be ready to use!

## 🤖 Usage

All commands are sent directly to the bot in your Telegram chat.

* `/start`: A welcome message that confirms the bot is running.
* `/help`: Displays a list of all available commands and their descriptions.
* `/movie <name>`: Searches for a movie.
* `/show <name>`: Searches for a TV series.
* `/language`: Opens a menu to change the bot's interface language (English, Portuguese, Spanish).
* `/streaming`: Lists all the streaming service codes recognized by the bot, which helps during the `/setup` process.
* `/setup`: Starts the guided configuration process again. This will overwrite your existing settings.

## 📁 Project Structure



.
├── config/             # (Auto-generated) Stores the persistent config.json file
├── logs/               # (Auto-generated) Stores log files
├── .env                # (You create) Your private Telegram Bot Token
├── .env.example        # Example environment file
├── bot.py              # The main Python script for the bot
├── docker-compose.yml  # Docker Compose file for easy deployment
├── Dockerfile          # Instructions to build the Docker image
└── requirements.txt    # Python dependencies


## 🤝 Contributing

Contributions are welcome! If you have ideas for new features, find a bug, or want to improve the code, feel free to:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/my-new-feature`).
3.  Make your changes.
4.  Commit your changes (`git commit -am 'Add some feature'`).
5.  Push to the branch (`git push origin feature/my-new-feature`).
6.  Create a new Pull Request.
