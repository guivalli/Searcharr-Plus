# Searcharr Plus - Your Smart Media Manager Bot 🤖

Inspired by `Searchrr` by toddrob99, **Searcharr Plus** is an enhanced Telegram bot designed to integrate seamlessly with Radarr and Sonarr. Its key feature is intelligence: before adding any media, the bot checks for its availability across your subscribed streaming services. This smart check prevents unnecessary downloads, saving you bandwidth and disk space.

Deployable in seconds with Docker, Searcharr Plus features a guided, interactive setup process right from your Telegram chat. It empowers administrators to effortlessly add new movies and shows (in standard or 4K quality), while allowing friends and family to request media or check library status without needing direct access to your services.

![Bot Screenshot](https://i.imgur.com/gGVV5G2.png) 

## ✨ Features

* **Smart Availability Check**: Automatically checks Plex, subscribed streaming services, and existing Overseerr requests before adding to Radarr/Sonarr.

* **Friend Request System**: Friends can use `/friendrequest` to ask for new media. Requests are sent to the admin for approval with simple "Accept" or "Decline" buttons.

* **Admin & Friend Roles**:

  * **Admins** have full control: add media, manage users, approve requests, and configure the bot.

  * **Friends** can check media availability and request new content, limited to 3 requests per day.

* **4K Support**: Admins can add media using separate 4K quality profiles and root folders in Radarr and Sonarr with the `/movie4k` and `/show4k` commands.

* **Secure & Session-Based Login**: User sessions are stored in memory and are **not** persistent. All users must re-authenticate with `/login` or an access code when the bot restarts. A `/logout` command is also available.

* **Easy Friend Management**: A simple, button-based `/friends` menu allows admins to add, remove, and list friends with unique, single-use access codes.

* **Interactive Setup**: A guided `/setup` menu with buttons allows for easy initial configuration and modification of individual services at any time.

* **Multi-Language Support**: Full interface translations for English, Portuguese, and Spanish, selectable with the `/language` command.

* **Docker-First Deployment**: Designed to be easily deployed and managed using Docker and Docker Compose.

## 🚀 Getting Started

Getting started with Searcharr Plus is simple. All you need is Docker and Docker Compose installed.

### 1. Project Structure

Create a directory for your bot and place the `bot.py` and `friend_requests.py` scripts inside it.


searcharr-plus/
├── bot.py
├── friend_requests.py
├── config/
└── logs/


The `config` and `logs` directories will be created automatically when you first run the bot.

### 2. Create the `.env` file

In the same `searcharr-plus` directory, create a file named `.env`. This file will store your essential secrets.


.env file
Your Telegram Bot Token from @BotFather
BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

The username and password for the bot's administrator
BOT_USER="your_admin_username"
BOT_PASSWORD="a_very_strong_password"


### 3. Create the `docker-compose.yml` file

Create a `docker-compose.yml` file in the `searcharr-plus` directory. This file will define how to run your bot in a container.


docker-compose.yml
version: '3.8'

services:
searcharr-bot:
container_name: searcharr-bot
build: .
restart: unless-stopped
volumes:
- ./:/app
environment:
- BOT_TOKEN=BOT 
T
​
 OKEN−BOT 
U
​
 SER={BOT_USER}
- BOT_PASSWORD=${BOT_PASSWORD}


### 4. Create the `Dockerfile`

Finally, create a `Dockerfile` in the same directory. This tells Docker how to build the image for your bot.


Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN pip install python-telegram-bot==13.15 python-dotenv requests plexapi

CMD ["python3", "bot.py"]


### 5. Run the Bot!

With all the files in place, open a terminal in the `searcharr-plus` directory and run:


docker-compose up -d --build


Your bot is now running! Open Telegram, find your bot, and send `/start`. It will guide you through the initial admin login and setup.

## ⚙️ Configuration

* **Login**: The first user to use `/login` can set themselves as the admin by providing the `BOT_USER` and `BOT_PASSWORD` from the `.env` file. Subsequent logins only require the password for the designated admin user.

* **/setup Command**: As the admin, you can use the `/setup` command at any time to configure all integrations. The interactive menu allows you to configure everything at once or just a specific service.

## 📋 Commands

### Admin Commands

* `/movie <title>`: Search for a movie and add it to Radarr.

* `/movie4k <title>`: Search for a movie and add it using your configured 4K profile.

* `/show <title>`: Search for a series and add it to Sonarr.

* `/show4k <title>`: Search for a series and add it using your configured 4K profile.

* `/check <movie|show> <title>`: Check if a media item is already on Plex, Radarr, or Sonarr.

* `/friends`: Open the friend management menu.

* `/setup`: Open the bot configuration menu.

* `/language`: Change the bot's display language.

* `/streaming`: List all available streaming service codes for configuration.

* `/debug <movie|show> <title>`: Run a step-by-step diagnostic check for a media item.

* `/logout`: End your session.

* `/help`: Show this help message.

### Friend Commands

* `/friendrequest <movie|show> <title>`: Request a movie or series. The request is sent to the admin for approval.

* `/check <movie|show> <title>`: Check if a media item is already on Plex, Radarr, or Sonarr.

* `/language`: Change the bot's display language.

* `/help`: Show this help message.

/movie <title>: Check the availability of a movie.

/show <title>: Check the availability of a series.

/check <movie|show> <title>: Check if a media item is already on Plex, Radarr, or Sonarr.

/language: Change the bot's display language.

/help: Show this help message.
![image](https://github.com/user-attachments/assets/ced297da-8caf-497b-8c97-ac5529e6ade8)

![image](https://github.com/user-attachments/assets/676616a9-a5fc-4585-8f51-639088a37416)
![image](https://github.com/user-attachments/assets/3d98a191-4804-47a2-9714-c9b72a03e7b2)

