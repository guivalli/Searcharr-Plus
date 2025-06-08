import os
import logging
from logging.handlers import RotatingFileHandler
import requests
import json
import sys
import uuid
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Updater, CommandHandler, CallbackContext,
    ConversationHandler, MessageHandler, Filters, CallbackQueryHandler
)
from dotenv import load_dotenv

try:
    from plexapi.server import PlexServer
    from plexapi.exceptions import Unauthorized, NotFound
    PLEX_AVAILABLE = True
except ImportError:
    PLEX_AVAILABLE = False

# --- Initial Setup ---
load_dotenv()
os.makedirs('logs', exist_ok=True)
os.makedirs('config', exist_ok=True)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file = 'logs/bot.log'
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# --- Configuration, Language, and Login Management ---
CONFIG_FILE = 'config/config.json'
CONFIG = {}
BOT_TOKEN = os.getenv('BOT_TOKEN')
BOT_USER = os.getenv('BOT_USER')
BOT_PASSWORD = os.getenv('BOT_PASSWORD')

# Conversation states
(GET_USERNAME, GET_PASSWORD) = range(2)
(
    GET_RADARR_URL, GET_RADARR_API, GET_RADARR_QUALITY, GET_RADARR_PATH,
    GET_SONARR_URL, GET_SONARR_API, GET_SONARR_QUALITY, GET_SONARR_PATH,
    GET_PLEX_TOKEN, GET_PLEX_URL,
    GET_TMDB_API_KEY,
    GET_STREAMING_REGION,
    ASK_OVERSEERR, GET_OVERSEERR_URL, GET_OVERSEERR_API,
    GET_STREAMING_SERVICES
) = range(2, 18)

# Translation Dictionary
translations = {
    'en': {
        "start_msg": "Hello! Please use `/login` (admin) or `/auth <code>` (friend) to use the bot.",
        "help_admin": "Admin Commands:\n/start - Welcome\n/login - Authenticate\n/logout - End session\n/movie <name> - Search for a movie\n/show <name> - Search for a series\n/status <movie|show> <name> - Check media status\n/setup - Guided configuration\n/language - Change language\n/streaming - List streaming service codes\n/friends - Manage friend access\n/debug <movie|show> <name> - Debug media checks\n/help - This message",
        "help_friend": "Available Commands:\n/movie <name> - Check if a movie is available on streaming\n/show <name> - Check if a series is available on streaming\n/status <movie|show> <name> - Check if media is on Plex or has been requested\n/logout - End your session",
        "friends_help": "Manage friend access:\n/friends add <name> - Create an access code for a friend.\n/friends remove <name> - Revoke a friend's access.\n/friends list - List all friends and their codes.",
        "friend_added": "✅ Friend '{name}' added. Their access code is: `{code}`\nPlease share it with them securely.",
        "friend_removed": "✅ Friend '{name}' has been removed.",
        "friend_list_title": "Friend List:",
        "friend_not_found": "❌ Friend '{name}' not found.",
        "no_friends": "You have not added any friends yet.",
        "auth_prompt": "Please provide your access code. Usage: /auth <your_code>",
        "auth_success": "✅ Friend access granted! Welcome. Use /help to see available commands.",
        "auth_fail": "❌ Invalid access code.",
        "not_available_friend": "Sorry, '{title}' is not available in the library yet.",
        "login_prompt_user": "Please enter your admin username.",
        "login_prompt_pass": "Please enter your password.",
        "login_success": "✅ Admin login successful! Use /help to see commands.",
        "login_fail": "❌ Invalid credentials. Please try /login again.",
        "login_needed": "You must be logged in. Please use /login or /auth.",
        "logout_success": "You have been logged out.",
        "already_logged_in": "You are already logged in.",
        "admin_only": "❌ This command is for admins only.",
        "streaming_help": "Available streaming service codes for setup:\n",
        "setup_needed": "The bot needs to be configured by the admin. Please contact them.",
        "setup_welcome": "Hello! Let's set up the bot.\nUse /cancel to stop or /skip to skip a section at any time.\n\nFirst, what is the full URL of your Radarr instance (e.g., http://192.168.1.10:7878)?",
        "setup_skip_radarr": "Skipping Radarr setup.",
        "setup_skip_sonarr": "Skipping Sonarr setup.",
        "setup_skip_plex": "Skipping Plex setup.",
        "setup_skip_tmdb": "Skipping TMDB & Region setup.",
        "setup_skip_overseerr": "Skipping Overseerr setup.",
        "setup_skip_streaming": "Skipping streaming services.",
        "radarr_not_configured": "Radarr is not configured. Use /setup to add it.",
        "sonarr_not_configured": "Sonarr is not configured. Use /setup to add it.",
        "setup_radarr_api": "Got it. What is your Radarr API Key?",
        "setup_radarr_quality": "What is the Radarr Quality Profile ID you want to use?",
        "setup_radarr_path": "What is the Radarr Root Folder Path (e.g., /movies/)?",
        "setup_sonarr_url": "Perfect. Now, what is the full URL of your Sonarr instance?",
        "setup_sonarr_api": "Got it. What is your Sonarr API Key?",
        "setup_sonarr_quality": "What is the Sonarr Quality Profile ID?",
        "setup_sonarr_path": "What is the Sonarr Root Folder Path (e.g., /tv/)?",
        "setup_plex_token": "Great. Please provide your Plex Authentication Token.",
        "setup_plex_url": "Please enter the full URL of your main Plex server (e.g., http://192.168.1.12:32400).",
        "setup_tmdb_api": "Excellent. Now, please provide your TMDB API Key (v3 Auth). This is required for checking streaming providers.",
        "setup_region": "Great. Now, please enter the two-letter country code for your primary streaming region (e.g., US for United States, GB for Great Britain). This will be used to check for streaming availability.",
        "setup_ask_overseerr": "Plex is configured. Do you also want to add Overseerr to check for pending requests? (yes/no)",
        "setup_overseerr_url": "Got it. What is the full URL for Overseerr?",
        "setup_overseerr_api": "And the Overseerr API Key?",
        "setup_streaming": "Finally, enter your subscribed streaming service codes, comma-separated (e.g., nfx,amp,dnp). Use /streaming for options.",
        "setup_finished": "Excellent! Saving configuration...",
        "setup_success": "✅ Configuration saved! The bot is ready.",
        "setup_canceled": "Setup canceled.",
        "language_prompt": "Please choose your language:",
        "language_set": "Language set to {lang}.",
        "usage_tip": "Usage: /{command} <name>",
        "status_usage_tip": "Usage: /status <movie|show> <name>",
        "searching": "🔍 Searching for '{query}'...",
        "no_results": "❌ No results found for '{query}'.",
        "status_checking": "Checking status for '{query}'...",
        "status_not_found": "Sorry, '{title}' could not be found or is not yet requested.",
        "status_available": "✅ '{title}' is already available!",
        "status_pending": "⏳ '{title}' has already been requested.",
        "status_streaming": "📺 '{title}' is on: {services}.",
        "status_adding": "'{title}' is not available. Sending request...",
        "status_verify_btn": "🔎 Verify Status",
        "add_success": "✅ Request for '{title}' sent to {service}!",
        "add_exists": "ℹ️ '{title}' already exists in {service}.",
        "add_fail": "❌ Failed to add '{title}' to {service}.",
        "add_lookup_fail": "❌ Failed to look up details for '{title}' on {service}.",
        "unexpected_error": "An unexpected error occurred.",
        "no_overview": "No overview available.",
        "add_movie_btn": "➕ Add Movie",
        "add_show_btn": "➕ Add Series",
        "cancel_btn": "❌ Cancel",
        "plex_found": "✅ '{title}' is already available on your Plex server: {server_name}.",
        "plex_not_available": "Plex integration is not available because the `plexapi` library is not installed.",
        "tmdb_not_configured": "TMDB API Key is not configured. Please run /setup.",
        "checking_tmdb": "Checking TMDB for streaming options...",
    }
}

def get_text(key, lang=None):
    if lang is None: lang = CONFIG.get('LANGUAGE', 'en')
    # Fallback to English if a key is not found in the selected language
    return translations.get(lang, translations['en']).get(key, translations['en'].get(key, f"_{key}_"))

# --- File and Decorator Functions ---
def load_config():
    """Load the configuration from the JSON file."""
    global CONFIG
    try:
        with open(CONFIG_FILE, 'r') as f:
            CONFIG = json.load(f)
        # Ensure default keys exist
        for key, default in [('LANGUAGE', 'en'), ('FRIENDS', {}), ('PLEX_URL', ''), ('OVERSEERR_URL', ''), ('TMDB_API_KEY', ''), ('STREAMING_REGION', 'US')]:
            if key not in CONFIG:
                CONFIG[key] = default
        logger.info("Configuration loaded from config.json")
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("config.json not found or invalid. Use /setup to configure.")
        CONFIG = {}
        return False

def save_config(new_config=None):
    """Save the current configuration to the JSON file."""
    global CONFIG
    if new_config:
        CONFIG = new_config
    # Ensure FRIENDS key exists before saving
    if 'FRIENDS' not in CONFIG:
        CONFIG['FRIENDS'] = {}
    with open(CONFIG_FILE, 'w') as f:
        json.dump(CONFIG, f, indent=4)
    load_config()

def check_login(func):
    """Decorator to ensure the user is logged in."""
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if not context.user_data.get('is_logged_in'):
            effective_message = update.callback_query.message if update.callback_query else update.message
            effective_message.reply_text(get_text('login_needed'))
            return
        return func(update, context, *args, **kwargs)
    return wrapper

def check_config(func):
    """Decorator to ensure the bot has been configured by the admin."""
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        # Bypass the check for friends; they don't need to configure anything.
        if context.user_data.get('role') == 'friend':
            return func(update, context, *args, **kwargs)
        
        # For admins, check if at least one core service is configured.
        is_configured = any(CONFIG.get(key) for key in ['RADARR_URL', 'SONARR_URL', 'PLEX_URL', 'OVERSEERR_URL', 'TMDB_API_KEY'])
        if not is_configured:
            lang = context.user_data.get('LANGUAGE', CONFIG.get('LANGUAGE', 'en'))
            if update.callback_query:
                update.callback_query.answer(get_text('setup_needed', lang), show_alert=True)
            elif update.message:
                update.message.reply_text(get_text('setup_needed', lang))
            return
        return func(update, context, *args, **kwargs)
    return wrapper

def check_admin(func):
    """Decorator to restrict a command to admin users only."""
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if context.user_data.get('role') != 'admin':
            effective_message = update.callback_query.message if update.callback_query else update.message
            effective_message.reply_text(get_text('admin_only'))
            return
        return func(update, context, *args, **kwargs)
    return wrapper

# --- API Interaction Functions ---
def api_request(method, url, **kwargs):
    """A helper function to make API requests."""
    try:
        response = requests.request(method, url, timeout=15, **kwargs)
        response.raise_for_status()
        if response.content and 'application/json' in response.headers.get('Content-Type', ''):
            return response.json()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during API request to {url}: {e}")
        return None

def search_radarr(query: str):
    """Search for movies on Radarr."""
    if not CONFIG.get('RADARR_URL'): return None
    return api_request('get', f"{CONFIG['RADARR_URL']}/api/v3/movie/lookup", headers={'X-Api-Key': CONFIG['RADARR_API_KEY']}, params={'term': query}) or []

def search_sonarr(query: str):
    """Search for series on Sonarr."""
    if not CONFIG.get('SONARR_URL'): return None
    return api_request('get', f"{CONFIG['SONARR_URL']}/api/v3/series/lookup", headers={'X-Api-Key': CONFIG['SONARR_API_KEY']}, params={'term': query}) or []

def check_plex_library(title_to_check):
    """Check if a title exists in the Plex library."""
    if not PLEX_AVAILABLE or not CONFIG.get('PLEX_URL'): return None
    try:
        plex = PlexServer(CONFIG['PLEX_URL'], CONFIG['PLEX_TOKEN'])
        server_name = plex.friendlyName
        logger.info(f"Checking Plex library '{server_name}' for title: {title_to_check}")
        
        results = plex.library.search(title=title_to_check, limit=1)
        
        if results:
            item = results[0]
            item.reload() 
            if hasattr(item, 'media') and item.media:
                logger.info(f"Found '{item.title}' with media files on Plex server '{server_name}'.")
                return {'status': 'available_on_plex', 'message': get_text('plex_found').format(title=item.title, server_name=server_name)}
        
        logger.info(f"'{title_to_check}' not found with media files in the Plex library.")
        return None
    except Exception as e:
        logger.error(f"Error checking Plex library: {e}"); return None

def check_tmdb_providers(tmdb_id, media_type, title):
    """Check for streaming providers using the TMDB API, focused on the user's region."""
    if not CONFIG.get('TMDB_API_KEY'):
        return {'status': 'error', 'message': get_text('tmdb_not_configured')}
    
    internal_media_type = 'tv' if media_type == 'show' else 'movie'
    url = f"https://api.themoviedb.org/3/{internal_media_type}/{tmdb_id}/watch/providers?api_key={CONFIG['TMDB_API_KEY']}"
    data = api_request('get', url)
    if not data or 'results' not in data:
        return None

    results = data['results']
    region = CONFIG.get('STREAMING_REGION', 'US').upper()
    
    if region in results and 'flatrate' in results[region]:
        provider_names = [p['provider_name'] for p in results[region]['flatrate']]
        logger.info(f"Streaming providers found in TMDB for region {region}: {provider_names}")
        
        subscribed_services = {s.lower() for s in CONFIG.get('SUBSCRIBED_SERVICES_CODES', [])}
        KEYWORD_MAP = {
            'nfx': ('netflix',), 'amp': ('amazon', 'prime video'), 'max': ('max', 'hbo'),
            'glb': ('globo',), 'pmp': ('paramount',), 'dnp': ('disney',),
            'apv': ('apple',), 'sp': ('star',)
        }

        available_on = []
        for provider_name in provider_names:
            provider_name_lower = provider_name.lower()
            for code in subscribed_services:
                if any(keyword in provider_name_lower for keyword in KEYWORD_MAP.get(code, ())):
                    available_on.append(provider_name)
                    break
        
        if available_on:
            unique_services = sorted(list(set(available_on)))
            logger.info(f"Match found in TMDB for region {region}! Media available on: {unique_services}")
            message = get_text('status_streaming').format(title=title, services=', '.join(unique_services))
            return {'status': 'available_on_streaming', 'message': message}

    logger.info(f"No matching providers found in the configured region ({region}) for '{title}'.")
    return None

def get_overseerr_status(tmdb_id, media_type):
    """Check for pending requests on Overseerr."""
    if not CONFIG.get('OVERSEERR_URL'): return None
    internal_media_type = 'tv' if media_type == 'show' else 'movie'
    url = f"{CONFIG.get('OVERSEERR_URL')}/api/v1/{internal_media_type}/{tmdb_id}"
    media_data = api_request('get', url, headers={'X-Api-Key': CONFIG['OVERSEERR_API_KEY']})
    if not media_data: return None
    title = media_data.get('title', media_data.get('name', ''))
    if (media_info := media_data.get('mediaInfo')) and (status_code := media_info.get('status')) in [1, 2, 3]:
        return {'status': 'pending_on_server', 'message': get_text('status_pending').format(title=title)}
    return None

def add_to_service(service, tmdb_id, title):
    """Add a movie or series to Radarr or Sonarr."""
    is_radarr = service == 'radarr'
    conf = {k.replace(f'{service.upper()}_', ''): v for k, v in CONFIG.items() if k.startswith(service.upper())}
    headers = {'X-Api-Key': conf['API_KEY']}
    lookup_endpoint = 'movie/lookup/tmdb' if is_radarr else 'series/lookup'
    params = {'tmdbId': tmdb_id} if is_radarr else {'term': f'tmdb:{tmdb_id}'}
    media_data_list = api_request('get', f"{conf['URL']}/api/v3/{lookup_endpoint}", headers=headers, params=params)

    if not media_data_list:
        return get_text('add_lookup_fail').format(title=title, service=service.title())

    media_data = media_data_list if is_radarr else media_data_list[0]
    title = media_data.get('title', title)

    if is_radarr:
        media_data.update({
            'qualityProfileId': int(conf['QUALITY_PROFILE_ID']), 'rootFolderPath': conf['ROOT_FOLDER_PATH'],
            'monitored': True, 'addOptions': {'searchForMovie': True}
        })
        endpoint = 'movie'
    else:
        media_data.update({
            'tvdbId': media_data.get('tvdbId'), 'qualityProfileId': int(conf['QUALITY_PROFILE_ID']),
            'rootFolderPath': conf['ROOT_FOLDER_PATH'], 'monitored': True,
            'addOptions': {'searchForMissingEpisodes': True, 'monitor': 'all'}
        })
        endpoint = 'series'

    response = api_request('post', f"{conf['URL']}/api/v3/{endpoint}", headers=headers, json=media_data)
    
    if isinstance(response, dict) and 'title' in response:
        return get_text('add_success').format(title=title, service=service.title())
    if isinstance(response, list) and response and 'errorMessage' in response[0] and 'already been added' in response[0]['errorMessage']:
        return get_text('add_exists').format(title=title, service=service.title())
        
    logger.error(f"Failed to add '{title}' to {service.title()}. Response: {response}")
    return get_text('add_fail').format(title=title, service=service.title())


def clear_search_data(context: CallbackContext):
    """Clear temporary search data from user_data."""
    for key in ['search_results', 'search_index', 'search_media_type', 'search_message_id', 'search_mode']:
        context.user_data.pop(key, None)

# --- Command Handlers ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('start_msg', CONFIG.get('LANGUAGE')))

def login_command(update: Update, context: CallbackContext):
    if context.user_data.get('is_logged_in'):
        update.message.reply_text(get_text('already_logged_in'))
        return ConversationHandler.END
    update.message.reply_text(get_text('login_prompt_user'))
    return GET_USERNAME

def get_username_for_login(update: Update, context: CallbackContext):
    context.user_data['login_user_attempt'] = update.message.text.strip()
    update.message.reply_text(get_text('login_prompt_pass'))
    return GET_PASSWORD

def check_password(update: Update, context: CallbackContext):
    user = context.user_data.pop('login_user_attempt', None)
    password = update.message.text.strip()
    if user == BOT_USER and password == BOT_PASSWORD:
        context.user_data.update({'is_logged_in': True, 'role': 'admin'})
        update.message.reply_text(get_text('login_success'))
    else:
        update.message.reply_text(get_text('login_fail'))
    return ConversationHandler.END

def auth_command(update: Update, context: CallbackContext):
    if not context.args: return update.message.reply_text(get_text('auth_prompt'))
    access_code = context.args[0]
    if any(access_code == data['code'] for data in CONFIG.get('FRIENDS', {}).values()):
        context.user_data.update({'is_logged_in': True, 'role': 'friend'})
        update.message.reply_text(get_text('auth_success'))
    else:
        update.message.reply_text(get_text('auth_fail'))

@check_login
def logout(update: Update, context: CallbackContext):
    context.user_data.clear()
    update.message.reply_text(get_text('logout_success'))

@check_login
def help_command(update: Update, context: CallbackContext):
    help_key = 'help_admin' if context.user_data.get('role') == 'admin' else 'help_friend'
    update.message.reply_text(get_text(help_key))

@check_login
def streaming_command(update: Update, context: CallbackContext):
    text = get_text('streaming_help') + "\n".join([f"`{code}`: {name}" for code, name in PROVIDER_MAP.items()])
    update.message.reply_text(text, parse_mode='Markdown')

@check_login
def language_command(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("🇬🇧 English", callback_data='lang_en'),
                 InlineKeyboardButton("🇵🇹 Português", callback_data='lang_pt'),
                 InlineKeyboardButton("🇪🇸 Español", callback_data='lang_es')]]
    update.message.reply_text(get_text('language_prompt'), reply_markup=InlineKeyboardMarkup(keyboard))

def set_language(update: Update, context: CallbackContext):
    query = update.callback_query; query.answer()
    lang_code = query.data.split('_')[1]
    CONFIG['LANGUAGE'] = lang_code
    save_config()
    lang_name = {"en": "English", "pt": "Português", "es": "Español"}.get(lang_code)
    query.edit_message_text(text=get_text('language_set').format(lang=lang_name))

@check_login
@check_admin
def friends_command(update: Update, context: CallbackContext):
    args = context.args
    if not args or args[0] not in ['add', 'remove', 'list']:
        return update.message.reply_text(get_text('friends_help'))
    command, *params = args
    if command == 'add' and params:
        name = params[0]
        code = str(uuid.uuid4())[:8]
        CONFIG.setdefault('FRIENDS', {})[name] = {'code': code}
        save_config()
        update.message.reply_text(get_text('friend_added').format(name=name, code=code), parse_mode='Markdown')
    elif command == 'remove' and params:
        name = params[0]
        if CONFIG.get('FRIENDS', {}).pop(name, None):
            save_config()
            update.message.reply_text(get_text('friend_removed').format(name=name))
        else:
            update.message.reply_text(get_text('friend_not_found').format(name=name))
    elif command == 'list':
        friends = CONFIG.get('FRIENDS', {})
        if not friends: return update.message.reply_text(get_text('no_friends'))
        message = get_text('friend_list_title') + "\n" + "\n".join([f"- {name}: `{data['code']}`" for name, data in friends.items()])
        update.message.reply_text(message, parse_mode='Markdown')

@check_login
@check_admin
def setup(update: Update, context: CallbackContext) -> int:
    context.user_data['setup_data'] = {}
    update.message.reply_text(get_text('setup_welcome'))
    return GET_RADARR_URL

def get_text_and_move(update, context, key, prompt_key, next_state):
    context.user_data['setup_data'][key] = update.message.text.strip()
    update.message.reply_text(get_text(prompt_key))
    return next_state

def skip_radarr(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_radarr'))
    for key in ['RADARR_URL', 'RADARR_API_KEY', 'RADARR_QUALITY_PROFILE_ID', 'RADARR_ROOT_FOLDER_PATH']:
        context.user_data['setup_data'][key] = ""
    update.message.reply_text(get_text('setup_sonarr_url'))
    return GET_SONARR_URL

def skip_sonarr(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_sonarr'))
    for key in ['SONARR_URL', 'SONARR_API_KEY', 'SONARR_QUALITY_PROFILE_ID', 'SONARR_ROOT_FOLDER_PATH']:
        context.user_data['setup_data'][key] = ""
    update.message.reply_text(get_text('setup_plex_token' if PLEX_AVAILABLE else 'setup_tmdb_api'))
    return GET_PLEX_TOKEN if PLEX_AVAILABLE else GET_TMDB_API_KEY

def skip_plex(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_plex'))
    for key in ['PLEX_TOKEN', 'PLEX_URL']:
        context.user_data['setup_data'][key] = ""
    update.message.reply_text(get_text('setup_tmdb_api'))
    return GET_TMDB_API_KEY

def skip_tmdb(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_tmdb'))
    for key in ['TMDB_API_KEY', 'STREAMING_REGION']:
        context.user_data['setup_data'][key] = ""
    update.message.reply_text(get_text('setup_ask_overseerr'))
    return ASK_OVERSEERR

def skip_overseerr(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_overseerr'))
    context.user_data['setup_data']['OVERSEERR_URL'] = ""
    context.user_data['setup_data']['OVERSEERR_API_KEY'] = ""
    update.message.reply_text(get_text('setup_streaming'))
    return GET_STREAMING_SERVICES

def skip_streaming(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_streaming'))
    context.user_data['setup_data']['SUBSCRIBED_SERVICES_CODES'] = []
    return finish_setup(update, context)

def get_plex_token(update: Update, context: CallbackContext):
    return get_text_and_move(update, context, 'PLEX_TOKEN', 'setup_plex_url', GET_PLEX_URL)

def get_plex_url(update: Update, context: CallbackContext):
    return get_text_and_move(update, context, 'PLEX_URL', 'setup_tmdb_api', GET_TMDB_API_KEY)
    
def get_tmdb_api_key(update: Update, context: CallbackContext):
    return get_text_and_move(update, context, 'TMDB_API_KEY', 'setup_region', GET_STREAMING_REGION)

def get_streaming_region(update: Update, context: CallbackContext):
    return get_text_and_move(update, context, 'STREAMING_REGION', 'setup_ask_overseerr', ASK_OVERSEERR)

def ask_overseerr(update: Update, context: CallbackContext):
    if update.message.text.lower() in ['yes', 'y']:
        update.message.reply_text(get_text('setup_overseerr_url'))
        return GET_OVERSEERR_URL
    else:
        return skip_overseerr(update, context)

def get_streaming_services(update: Update, context: CallbackContext):
    context.user_data['setup_data']['SUBSCRIBED_SERVICES_CODES'] = [c.strip().lower() for c in update.message.text.split(',')]
    return finish_setup(update, context)

def finish_setup(update, context):
    update.message.reply_text(get_text('setup_finished'))
    context.user_data['setup_data']['LANGUAGE'] = CONFIG.get('LANGUAGE', 'en')
    save_config(new_config=context.user_data.pop('setup_data'))
    update.message.reply_text(get_text('setup_success'))
    return ConversationHandler.END

def cancel_setup(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_canceled'))
    context.user_data.pop('setup_data', None)
    return ConversationHandler.END

@check_config
@check_login
def search_media(update: Update, context: CallbackContext, media_type: str):
    """Handles /movie and /show commands."""
    if media_type == 'movie' and not CONFIG.get('RADARR_URL'): return update.message.reply_text(get_text('radarr_not_configured'))
    if media_type == 'show' and not CONFIG.get('SONARR_URL'): return update.message.reply_text(get_text('sonarr_not_configured'))
    query_str = ' '.join(context.args)
    if not query_str: return update.message.reply_text(get_text('usage_tip').format(command=media_type))
    msg = update.message.reply_text(get_text('searching').format(query=query_str))
    results = search_radarr(query_str) if media_type == 'movie' else search_sonarr(query_str)
    msg.delete()
    if not results: return update.message.reply_text(get_text('no_results').format(query=query_str))
    clear_search_data(context)
    context.user_data.update({
        'search_results': results, 
        'search_index': 0, 
        'search_media_type': media_type,
        'search_mode': 'add'
    })
    display_media_result(update, context)

@check_login
def status_command(update: Update, context: CallbackContext):
    """Handles the /status command by searching TMDB and showing an interactive menu."""
    args = context.args
    if not args or len(args) < 2 or args[0].lower() not in ['movie', 'show']:
        return update.message.reply_text(get_text('status_usage_tip'))

    media_type = args[0].lower()
    query_str = ' '.join(args[1:])
    
    msg = update.message.reply_text(get_text('searching').format(query=query_str))
    
    # Use the more reliable TMDB search for the initial lookup
    results = search_tmdb(query_str, media_type)
    msg.delete()

    if not results:
        return update.message.reply_text(get_text('no_results').format(query=query_str))

    clear_search_data(context)
    context.user_data.update({
        'search_results': results, 
        'search_index': 0,
        'search_media_type': media_type,
        'search_mode': 'status'
    })
    display_media_result(update, context)

def display_media_result(update: Update, context: CallbackContext):
    """A unified function to display search results for /movie, /show, and /status."""
    query = update.callback_query
    results = context.user_data.get('search_results', [])
    index = context.user_data.get('search_index', 0)
    media_type = context.user_data.get('search_media_type')
    search_mode = context.user_data.get('search_mode')

    item = results[index]

    # Handle both Radarr/Sonarr (add mode) and TMDB (status mode) search results
    is_tmdb_search = 'first_air_date' in item or 'release_date' in item
    
    if is_tmdb_search:
        is_movie = media_type == 'movie'
        title = item.get('title') if is_movie else item.get('name')
        date_key = 'release_date' if is_movie else 'first_air_date'
        year = item.get(date_key, 'N/A')[:4] if item.get(date_key) else 'N/A'
        tmdb_id = item.get('id')
        poster_path = item.get('poster_path')
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else f"https://placehold.co/500x750/1c1c1e/ffffff?text={requests.utils.quote(title or 'No Title')}"
    else: # Radarr/Sonarr search result
        title = item.get('title')
        year = item.get('year')
        tmdb_id = item.get('tmdbId')
        poster_path = next((img.get('remoteUrl') or img.get('url') for img in item.get('images', []) if img.get('coverType') == 'poster'), None)
        poster_url = poster_path if poster_path and poster_path.startswith('http') else f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else f"https://placehold.co/500x750/1c1c1e/ffffff?text={requests.utils.quote(title or 'No Title')}"

    overview = (item.get('overview') or get_text('no_overview'))
    if len(overview) > 700: overview = overview[:700] + '...'
    
    caption = f"*{title} ({year})*\n\n{overview}"
    
    nav_row = [
        InlineKeyboardButton("⬅️" if index > 0 else " ", callback_data="nav_prev" if index > 0 else "noop"),
        InlineKeyboardButton("ℹ️ TMDB", url=f"https://www.themoviedb.org/{'tv' if media_type == 'show' else 'movie'}/{tmdb_id}"),
        InlineKeyboardButton("➡️" if index < len(results) - 1 else " ", callback_data="nav_next" if index < len(results) - 1 else "noop")
    ]
    
    keyboard = [nav_row]
    
    if search_mode == 'add':
        btn_text = get_text('add_movie_btn' if media_type == 'movie' else 'add_show_btn')
        callback_data = f"add_{media_type}_{tmdb_id}"
        if context.user_data.get('role') == 'admin':
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
    elif search_mode == 'status':
        btn_text = get_text('status_verify_btn')
        callback_data = f"status_verify_{media_type}_{tmdb_id}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
        
    keyboard.append([InlineKeyboardButton(get_text('cancel_btn'), callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    media = InputMediaPhoto(media=poster_url, caption=caption, parse_mode='Markdown')
    effective_message = query.message if query else update.message
    
    if query:
        try:
            query.edit_message_media(media=media, reply_markup=reply_markup)
        except Exception as e:
            if 'Message is not modified' not in str(e): logger.warning(f"Error editing media message: {e}")
    else:
        message = effective_message.reply_photo(photo=poster_url, caption=caption, reply_markup=reply_markup, parse_mode='Markdown')
        context.user_data['search_message_id'] = message.message_id

@check_config
@check_login
def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query; query.answer()
    action, *payload = query.data.split('_')

    if action == "noop": return
    if action == "lang": return set_language(update, context)
    if action == "cancel":
        query.message.delete(); clear_search_data(context); return

    if action == "nav":
        context.user_data['search_index'] += 1 if payload[0] == "next" else -1
        return display_media_result(update, context)
    
    results = context.user_data.get('search_results', [])
    index = context.user_data.get('search_index', 0)
    item = results[index]

    if action == "status" and payload[0] == "verify":
        media_type, tmdb_id_str = payload[1], payload[2]
        tmdb_id = int(tmdb_id_str)
        title_to_check = item.get('title') if media_type == 'movie' else item.get('name')

        query.message.delete()
        status_msg = query.message.reply_text(get_text('status_checking').format(query=title_to_check))
        
        if plex_lib_check := check_plex_library(title_to_check):
            return status_msg.edit_text(plex_lib_check['message'])

        if overseerr_check := get_overseerr_status(tmdb_id, media_type):
            return status_msg.edit_text(overseerr_check['message'])

        return status_msg.edit_text(get_text('status_not_found').format(title=title_to_check))

    if action == "add":
        media_type, tmdb_id_str = payload
        tmdb_id = int(tmdb_id_str)
        title_to_check = item.get('title')

        query.message.delete()
        clear_search_data(context)
        
        status_msg = query.message.reply_text(get_text('status_checking').format(query=title_to_check))
        
        if plex_lib_check := check_plex_library(title_to_check):
            return status_msg.edit_text(plex_lib_check['message'])
        
        status_msg.edit_text(get_text('checking_tmdb'))
        tmdb_check = check_tmdb_providers(tmdb_id, media_type, title_to_check)
        if tmdb_check:
            return status_msg.edit_text(tmdb_check['message'])

        if overseerr_check := get_overseerr_status(tmdb_id, media_type):
            return status_msg.edit_text(overseerr_check['message'])

        if context.user_data.get('role') == 'admin':
            status_msg.edit_text(get_text('status_adding').format(title=title_to_check))
            final_message = add_to_service('radarr' if media_type == 'movie' else 'sonarr', tmdb_id, title_to_check)
        else: 
            final_message = get_text('not_available_friend').format(title=title_to_check)
        
        status_msg.edit_text(final_message)

@check_login
@check_admin
def debug_media(update: Update, context: CallbackContext):
    """Provides a step-by-step debug of the media checking process."""
    if not context.args or len(context.args) < 2 or context.args[0] not in ['movie', 'show']:
        update.message.reply_text("Usage: /debug <movie|show> <query>")
        return
    
    media_type = context.args[0]
    query_str = ' '.join(context.args[1:])
    chat = update.effective_chat
    
    def report(message):
        context.bot.send_message(chat.id, f"🐞 {message}")

    report(f"Starting debug for {media_type} '{query_str}'...")

    report(f"Searching {media_type} on {'Radarr' if media_type == 'movie' else 'Sonarr'}...")
    results = search_radarr(query_str) if media_type == 'movie' else search_sonarr(query_str)
    if not results:
        report("No results found in Radarr/Sonarr. Aborting.")
        return
    
    item = results[0] 
    title_to_check = item.get('title')
    year_to_check = item.get('year')
    tmdb_id = item.get('tmdbId')
    report(f"Found '{title_to_check}' ({year_to_check}) with TMDB ID {tmdb_id}.")

    report("---")
    report("Checking Plex library...")
    if (plex_lib_check := check_plex_library(title_to_check)):
        report(f"SUCCESS: Found in Plex library. Message: {plex_lib_check['message']}")
        return report("Debug finished.")
    report("Not found in Plex library.")

    report("---")
    report("Checking TMDB providers...")
    if (tmdb_check := check_tmdb_providers(tmdb_id, media_type, title_to_check)):
         if tmdb_check.get('status') == 'error':
             report(f"ERROR: {tmdb_check['message']}")
         else:
             report(f"SUCCESS: Found via TMDB. Message: {tmdb_check['message']}")
         return report("Debug finished.")
    report("No matching provider found via TMDB.")
    
    report("---")
    report("Debug finished.")

def main():
    if not all([BOT_TOKEN, BOT_USER, BOT_PASSWORD]):
        logger.critical("!!! BOT_TOKEN, BOT_USER, and BOT_PASSWORD are required in .env file.")
        return

    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher
    
    login_conv = ConversationHandler(
        entry_points=[CommandHandler('login', login_command)],
        states={
            GET_USERNAME: [MessageHandler(Filters.text & ~Filters.command, get_username_for_login)],
            GET_PASSWORD: [MessageHandler(Filters.text & ~Filters.command, check_password)],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    setup_states_map = {
        GET_RADARR_URL: (lambda u,c: get_text_and_move(u,c,'RADARR_URL','setup_radarr_api',GET_RADARR_API)),
        GET_RADARR_API: (lambda u,c: get_text_and_move(u,c,'RADARR_API_KEY','setup_radarr_quality',GET_RADARR_QUALITY)),
        GET_RADARR_QUALITY: (lambda u,c: get_text_and_move(u,c,'RADARR_QUALITY_PROFILE_ID','setup_radarr_path',GET_RADARR_PATH)),
        GET_RADARR_PATH: (lambda u,c: get_text_and_move(u,c,'RADARR_ROOT_FOLDER_PATH','setup_sonarr_url',GET_SONARR_URL)),
        GET_SONARR_URL: (lambda u,c: get_text_and_move(u,c,'SONARR_URL','setup_sonarr_api',GET_SONARR_API)),
        GET_SONARR_API: (lambda u,c: get_text_and_move(u,c,'SONARR_API_KEY','setup_sonarr_quality',GET_SONARR_QUALITY)),
        GET_SONARR_QUALITY: (lambda u,c: get_text_and_move(u,c,'SONARR_QUALITY_PROFILE_ID','setup_sonarr_path',GET_SONARR_PATH)),
        GET_SONARR_PATH: (lambda u,c: get_text_and_move(u,c,'SONARR_ROOT_FOLDER_PATH','setup_plex_token' if PLEX_AVAILABLE else 'setup_tmdb_api', GET_PLEX_TOKEN if PLEX_AVAILABLE else GET_TMDB_API_KEY)),
        GET_PLEX_TOKEN: get_plex_token,
        GET_PLEX_URL: get_plex_url,
        GET_TMDB_API_KEY: get_tmdb_api_key,
        GET_STREAMING_REGION: get_streaming_region,
        ASK_OVERSEERR: ask_overseerr,
        GET_OVERSEERR_URL: (lambda u,c: get_text_and_move(u,c,'OVERSEERR_URL','setup_overseerr_api',GET_OVERSEERR_API)),
        GET_OVERSEERR_API: (lambda u,c: get_text_and_move(u,c,'OVERSEERR_API_KEY','setup_streaming',GET_STREAMING_SERVICES)),
        GET_STREAMING_SERVICES: get_streaming_services,
    }

    setup_conv = ConversationHandler(
        entry_points=[CommandHandler('setup', setup)],
        states={
            state: [MessageHandler(Filters.text & ~Filters.command, func)] for state, func in setup_states_map.items()
        },
        fallbacks=[CommandHandler('cancel', cancel_setup)]
    )
    # Add /skip handlers for each setup section
    radarr_range = range(GET_RADARR_URL, GET_SONARR_URL)
    sonarr_range = range(GET_SONARR_URL, GET_PLEX_TOKEN)
    plex_range = [GET_PLEX_TOKEN, GET_PLEX_URL] if PLEX_AVAILABLE else []
    tmdb_range = [GET_TMDB_API_KEY, GET_STREAMING_REGION]
    overseerr_range = [ASK_OVERSEERR, GET_OVERSEERR_URL, GET_OVERSEERR_API]
    streaming_range = [GET_STREAMING_SERVICES]

    for state, handlers in setup_conv.states.items():
        if state in radarr_range:
            handlers.append(CommandHandler('skip', skip_radarr))
        if state in sonarr_range:
            handlers.append(CommandHandler('skip', skip_sonarr))
        if state in plex_range:
            handlers.append(CommandHandler('skip', skip_plex))
        if state in tmdb_range:
            handlers.append(CommandHandler('skip', skip_tmdb))
        if state in overseerr_range:
            handlers.append(CommandHandler('skip', skip_overseerr))
        if state in streaming_range:
            handlers.append(CommandHandler('skip', skip_streaming))
    
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(login_conv)
    dispatcher.add_handler(CommandHandler("logout", logout))
    dispatcher.add_handler(CommandHandler("auth", auth_command))
    dispatcher.add_handler(CommandHandler("friends", friends_command))
    dispatcher.add_handler(setup_conv)
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("streaming", streaming_command))
    dispatcher.add_handler(CommandHandler("language", language_command))
    dispatcher.add_handler(CommandHandler("status", status_command))
    dispatcher.add_handler(CommandHandler("movie", lambda u,c: search_media(u,c,'movie')))
    dispatcher.add_handler(CommandHandler("show", lambda u,c: search_media(u,c,'show')))
    dispatcher.add_handler(CommandHandler("debug", debug_media))
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    
    load_config()
    logger.info("Bot started and listening...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.critical(f"Bot encountered a fatal error: {e}", exc_info=True)
        sys.exit(1)
