import os
import logging
from logging.handlers import RotatingFileHandler
import requests
import json
import sys
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Updater, CommandHandler, CallbackContext,
    ConversationHandler, MessageHandler, Filters, CallbackQueryHandler
)
from dotenv import load_dotenv

# --- Configuração Inicial ---
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
if logger.hasHandlers(): logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# --- Gerenciamento de Configuração, Idioma e Login ---
CONFIG_FILE = 'config/config.json'
CONFIG = {}
BOT_TOKEN = os.getenv('BOT_TOKEN')
BOT_USER = os.getenv('BOT_USER')
BOT_PASSWORD = os.getenv('BOT_PASSWORD')
SUBSCRIBED_PROVIDER_IDS = set()

# Estados da conversa
(GET_USERNAME, GET_PASSWORD) = range(2)
(
    GET_RADARR_URL, GET_RADARR_API, GET_RADARR_QUALITY, GET_RADARR_PATH,
    GET_SONARR_URL, GET_SONARR_API, GET_SONARR_QUALITY, GET_SONARR_PATH,
    GET_OVERSEERR_URL, GET_OVERSEERR_API,
    GET_STREAMING_SERVICES, GET_COUNTRY_CODE
) = range(2, 14)

# Dicionário de Traduções (COMPLETO)
translations = {
    'en': {
        "start_msg": "Hello! Please /login to use the bot.",
        "help_text": "Available commands:\n/start - Welcome message\n/login - Authenticate\n/logout - End session\n/movie <name> - Search movie\n/show <name> - Search series\n/setup - Guided configuration\n/language - Change language\n/streaming - List codes\n/help - This message",
        "streaming_help": "Available streaming service codes for setup:\n",
        "setup_needed": "Bot needs to be configured. Use /setup.",
        "setup_welcome": "Hello! Let's set up the bot.\nUse /cancel to stop or /skip to skip a section (Radarr/Sonarr).\n\nWhat is the full URL of your Radarr (e.g., http://192.168.1.10:7878)?",
        "setup_skip_radarr": "Skipping Radarr setup.",
        "setup_skip_sonarr": "Skipping Sonarr setup.",
        "radarr_not_configured": "Radarr is not configured. Use /setup to add it.",
        "sonarr_not_configured": "Sonarr is not configured. Use /setup to add it.",
        "setup_radarr_api": "Got it. Radarr API Key?",
        "setup_radarr_quality": "Radarr Quality Profile ID?",
        "setup_radarr_path": "Radarr Root Folder Path (e.g., /movies/)?",
        "setup_sonarr_url": "Perfect. Now, Sonarr's full URL?",
        "setup_sonarr_api": "Got it. Sonarr API Key?",
        "setup_sonarr_quality": "Sonarr Quality Profile ID?",
        "setup_sonarr_path": "Sonarr Root Folder Path (e.g., /tv/)?",
        "setup_overseerr_url": "Almost there! Overseerr's full URL?",
        "setup_overseerr_api": "And the Overseerr API Key?",
        "setup_streaming": "Enter your streaming service codes, comma-separated (e.g., nfx,amp,max). Use /streaming for options.",
        "setup_country": "Last question: Your country code for JustWatch (e.g., US, BR)?",
        "setup_finished": "Excellent! Saving configuration...",
        "setup_success": "✅ Configuration saved! The bot is ready. Change language with /language.",
        "setup_canceled": "Setup canceled.",
        "language_prompt": "Please choose your language:",
        "language_set": "Language set to {lang}.",
        "usage_tip": "Usage: /{command} <name>",
        "searching": "🔍 Searching for '{query}'...",
        "no_results": "❌ No results found for '{query}'.",
        "status_checking": "Checking status...",
        "status_available": "✅ '{title}' is already available!",
        "status_pending": "⏳ '{title}' has already been requested.",
        "status_streaming": "📺 '{title}' is on: {services}.",
        "status_adding": "'{title}' is not available. Sending request...",
        "add_success": "✅ Request for '{title}' sent to {service}!",
        "add_exists": "ℹ️ '{title}' already exists in {service}.",
        "add_fail": "❌ Failed to add '{title}' to {service}.",
        "add_lookup_fail": "❌ Failed to look up details for '{title}' on {service}.",
        "unexpected_error": "An unexpected error occurred.",
        "no_overview": "No overview available.",
        "add_movie_btn": "➕ Add Movie",
        "add_show_btn": "➕ Add Series",
        "cancel_btn": "❌ Cancel",
        "login_prompt_user": "Please enter your username.",
        "login_prompt_pass": "Please enter your password.",
        "login_success": "✅ Login successful! Use /help to see commands.",
        "login_fail": "❌ Invalid credentials. Please try /login again.",
        "login_needed": "You must be logged in. Please use /login.",
        "logout_success": "You have been logged out.",
        "already_logged_in": "You are already logged in.",
    },
    'pt': {
        "start_msg": "Olá! Por favor, use /login para usar o bot.",
        "help_text": "Comandos disponíveis:\n/start - Mensagem de boas-vindas\n/login - Autenticar\n/logout - Encerrar sessão\n/movie <nome> - Procurar filme\n/show <nome> - Procurar série\n/setup - Configuração guiada\n/language - Mudar idioma\n/streaming - Listar códigos\n/help - Esta mensagem",
        "streaming_help": "Códigos de serviços de streaming disponíveis para a configuração:\n",
        "setup_needed": "O bot precisa ser configurado. Use /setup.",
        "setup_welcome": "Olá! Vamos configurar o bot.\nUse /cancel para parar ou /skip para pular uma seção (Radarr/Sonarr).\n\nQual a URL completa do seu Radarr (ex: http://192.168.1.10:7878)?",
        "setup_skip_radarr": "Pulando configuração do Radarr.",
        "setup_skip_sonarr": "Pulando configuração do Sonarr.",
        "radarr_not_configured": "O Radarr não está configurado. Use /setup para adicioná-lo.",
        "sonarr_not_configured": "O Sonarr não está configurado. Use /setup para adicioná-lo.",
        "setup_radarr_api": "Ok. Chave de API (API Key) do Radarr?",
        "setup_radarr_quality": "ID do Perfil de Qualidade do Radarr?",
        "setup_radarr_path": "Caminho da Pasta Raiz do Radarr (ex: /movies/)?",
        "setup_sonarr_url": "Perfeito. Agora, a URL completa do Sonarr?",
        "setup_sonarr_api": "Ok. Chave de API (API Key) do Sonarr?",
        "setup_sonarr_quality": "ID do Perfil de Qualidade do Sonarr?",
        "setup_sonarr_path": "Caminho da Pasta Raiz do Sonarr (ex: /tv/)?",
        "setup_overseerr_url": "Quase lá! URL completa do seu Overseerr?",
        "setup_overseerr_api": "E a Chave de API do Overseerr?",
        "setup_streaming": "Informe os códigos dos seus serviços de streaming, separados por vírgula (ex: nfx,amp,max). Use /streaming para opções.",
        "setup_country": "Última pergunta: Código do seu país para o JustWatch (ex: BR, US)?",
        "setup_finished": "Excelente! Salvando configuração...",
        "setup_success": "✅ Configuração salva! O bot está pronto. Mude o idioma com /language.",
        "setup_canceled": "Configuração cancelada.",
        "language_prompt": "Por favor, escolha seu idioma:",
        "language_set": "Idioma alterado para {lang}.",
        "usage_tip": "Uso: /{command} <nome>",
        "searching": "🔍 Buscando por '{query}'...",
        "no_results": "❌ Nenhum resultado encontrado para '{query}'.",
        "status_checking": "Verificando status...",
        "status_available": "✅ '{title}' já está disponível!",
        "status_pending": "⏳ '{title}' já foi solicitado.",
        "status_streaming": "📺 '{title}' está em: {services}.",
        "status_adding": "'{title}' não está disponível. Enviando pedido...",
        "add_success": "✅ Pedido para '{title}' enviado ao {service}!",
        "add_exists": "ℹ️ '{title}' já existe no {service}.",
        "add_fail": "❌ Falha ao adicionar '{title}' ao {service}.",
        "add_lookup_fail": "❌ Falha ao buscar detalhes de '{title}' no {service}.",
        "unexpected_error": "Ocorreu um erro inesperado.",
        "no_overview": "Nenhuma sinopse disponível.",
        "add_movie_btn": "➕ Adicionar Filme",
        "add_show_btn": "➕ Adicionar Série",
        "cancel_btn": "❌ Cancelar",
        "login_prompt_user": "Por favor, digite seu nome de usuário.",
        "login_prompt_pass": "Por favor, digite sua senha.",
        "login_success": "✅ Login realizado com sucesso! Use /help para ver os comandos.",
        "login_fail": "❌ Credenciais inválidas. Tente /login novamente.",
        "login_needed": "Você precisa estar logado. Por favor, use /login.",
        "logout_success": "Você foi desconectado.",
        "already_logged_in": "Você já está logado.",
    },
    'es': {
        "start_msg": "¡Hola! Por favor, usa /login para utilizar el bot.",
        "help_text": "Comandos disponibles:\n/start - Mensaje de bienvenida\n/login - Autenticarse\n/logout - Cerrar sesión\n/movie <nombre> - Buscar película\n/show <nombre> - Buscar serie\n/setup - Configuración guiada\n/language - Cambiar idioma\n/streaming - Listar códigos\n/help - Este mensaje",
        "streaming_help": "Códigos de servicios de streaming disponibles para la configuración:\n",
        "setup_needed": "El bot necesita ser configurado. Usa /setup.",
        "setup_welcome": "¡Hola! Vamos a configurar el bot.\nUsa /cancel para detenerte o /skip para saltar una sección (Radarr/Sonarr).\n\n¿Cuál es la URL completa de tu Radarr (ej: http://192.168.1.10:7878)?",
        "setup_skip_radarr": "Saltando configuración de Radarr.",
        "setup_skip_sonarr": "Saltando configuración de Sonarr.",
        "radarr_not_configured": "Radarr no está configurado. Usa /setup para agregarlo.",
        "sonarr_not_configured": "Sonarr no está configurado. Usa /setup para agregarlo.",
        "setup_radarr_api": "Entendido. ¿Clave de API (API Key) de Radarr?",
        "setup_radarr_quality": "¿ID del Perfil de Calidad de Radarr?",
        "setup_radarr_path": "¿Ruta de la Carpeta Raíz de Radarr (ej: /movies/)?",
        "setup_sonarr_url": "Perfecto. Ahora, ¿URL completa de Sonarr?",
        "setup_sonarr_api": "Entendido. ¿Clave de API (API Key) de Sonarr?",
        "setup_sonarr_quality": "¿ID del Perfil de Calidad de Sonarr?",
        "setup_sonarr_path": "¿Ruta de la Carpeta Raíz de Sonarr (ej: /tv/)?",
        "setup_overseerr_url": "¡Casi listo! ¿URL completa de tu Overseerr?",
        "setup_overseerr_api": "¿Y la Clave de API de Overseerr?",
        "setup_streaming": "Introduce los códigos de tus servicios de streaming, separados por comas (ej: nfx,amp,max). Usa /streaming para opciones.",
        "setup_country": "Última pregunta: ¿Código de tu país para JustWatch (ej: ES, MX)?",
        "setup_finished": "¡Excelente! Guardando configuración...",
        "setup_success": "✅ ¡Configuración guardada! El bot está listo. Cambia el idioma con /language.",
        "setup_canceled": "Configuración cancelada.",
        "language_prompt": "Por favor, elige tu idioma:",
        "language_set": "Idioma cambiado a {lang}.",
        "usage_tip": "Uso: /{command} <nombre>",
        "searching": "🔍 Buscando '{query}'...",
        "no_results": "❌ No se encontraron resultados para '{query}'.",
        "status_checking": "Verificando estado...",
        "status_available": "✅ ¡'{title}' ya está disponible!",
        "status_pending": "⏳ '{title}' ya ha sido solicitado.",
        "status_streaming": "📺 '{title}' está en: {services}.",
        "status_adding": "'{title}' no está disponible. Enviando solicitud...",
        "add_success": "✅ ¡Solicitud para '{title}' enviada a {service}!",
        "add_exists": "ℹ️ '{title}' ya existe en {service}.",
        "add_fail": "❌ Fallo al agregar '{title}' a {service}.",
        "add_lookup_fail": "❌ Fallo al buscar detalles para '{title}' en {service}.",
        "unexpected_error": "Ocurrió un error inesperado.",
        "no_overview": "No hay sinopsis disponible.",
        "add_movie_btn": "➕ Añadir Película",
        "add_show_btn": "➕ Añadir Serie",
        "cancel_btn": "❌ Cancelar",
        "login_prompt_user": "Por favor, introduce tu nombre de usuario.",
        "login_prompt_pass": "Por favor, introduce tu contraseña.",
        "login_success": "✅ ¡Inicio de sesión exitoso! Usa /help para ver los comandos.",
        "login_fail": "❌ Credenciales inválidas. Intenta /login de nuevo.",
        "login_needed": "Debes iniciar sesión. Por favor, usa /login.",
        "logout_success": "Has cerrado la sesión.",
        "already_logged_in": "Ya has iniciado sesión.",
    }
}

def get_text(key, lang=None):
    if lang is None: lang = CONFIG.get('LANGUAGE', 'en')
    return translations.get(lang, translations['en']).get(key, f"_{key}_")

PROVIDER_MAP = {
    'nfx': 'Netflix', 'amp': 'Amazon Prime Video', 'max': 'Max', 'glb': 'GloboPlay',
    'pmp': 'Paramount+', 'dnp': 'Disney+', 'apv': 'Apple TV+', 'sp': 'Star+'
}
PROVIDER_IDS = {
    'nfx': 8, 'amp': 119, 'max': 384, 'glb': 307, 'pmp': 531,
    'dnp': 337, 'apv': 350, 'sp': 619, 'max_new': 1899
}

def load_config():
    global CONFIG, SUBSCRIBED_PROVIDER_IDS
    try:
        with open(CONFIG_FILE, 'r') as f: CONFIG = json.load(f)
        if 'LANGUAGE' not in CONFIG: CONFIG['LANGUAGE'] = 'en'
        subscribed_codes = CONFIG.get('SUBSCRIBED_SERVICES_CODES', [])
        SUBSCRIBED_PROVIDER_IDS = {PROVIDER_IDS[code] for code in subscribed_codes if code in PROVIDER_IDS}
        if 'max' in subscribed_codes: SUBSCRIBED_PROVIDER_IDS.add(1899)
        logger.info("Configuração carregada de config.json")
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("config.json não encontrado ou inválido. Use /setup para configurar.")
        CONFIG = {}; SUBSCRIBED_PROVIDER_IDS = set()
        return False

def save_config(new_config=None):
    global CONFIG
    if new_config: CONFIG = new_config
    with open(CONFIG_FILE, 'w') as f: json.dump(CONFIG, f, indent=4)
    load_config()

def check_login(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if not context.user_data.get('is_logged_in'):
            effective_message = update.callback_query.message if update.callback_query else update.message
            effective_message.reply_text(get_text('login_needed'))
            return
        return func(update, context, *args, **kwargs)
    return wrapper

def check_config(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if not CONFIG:
            lang = context.user_data.get('LANGUAGE', 'en')
            if update.callback_query: update.callback_query.answer(get_text('setup_needed', lang), show_alert=True)
            elif update.message: update.message.reply_text(get_text('setup_needed', lang))
            return
        return func(update, context, *args, **kwargs)
    return wrapper

def api_request(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=10, **kwargs)
        response.raise_for_status()
        if response.content and 'application/json' in response.headers.get('Content-Type', ''): return response.json()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição para {url}: {e}"); return None

def search_radarr(query: str):
    if not CONFIG.get('RADARR_URL'): return None
    return api_request('get', f"{CONFIG['RADARR_URL']}/api/v3/movie/lookup", headers={'X-Api-Key': CONFIG['RADARR_API_KEY']}, params={'term': query}) or []

def search_sonarr(query: str):
    if not CONFIG.get('SONARR_URL'): return None
    return api_request('get', f"{CONFIG['SONARR_URL']}/api/v3/series/lookup", headers={'X-Api-Key': CONFIG['SONARR_API_KEY']}, params={'term': query}) or []

def get_overseerr_status_by_id(tmdb_id: int, media_type: str):
    media_data = api_request('get', f"{CONFIG['OVERSEERR_URL']}/api/v1/{'tv' if media_type == 'show' else 'movie'}/{tmdb_id}", headers={'X-Api-Key': CONFIG['OVERSEERR_API_KEY']})
    if media_data is None: return {'status': 'not_available', 'title': f'ID {tmdb_id}'}
    title = media_data.get('title', media_data.get('name', ''))
    if media_info := media_data.get('mediaInfo'):
        if media_info.get('status') in [4, 5]: return {'status': 'available_on_server', 'message': get_text('status_available').format(title=title)}
        if media_info.get('status') in [1, 2, 3]: return {'status': 'pending_on_server', 'message': get_text('status_pending').format(title=title)}
    if watch_providers := media_data.get('watchProviders'):
        providers = next((c.get('flatrate', []) for c in watch_providers if c.get('iso_3166_1') == CONFIG['JUSTWATCH_COUNTRY_CODE']), []) if isinstance(watch_providers, list) else watch_providers.get(CONFIG['JUSTWATCH_COUNTRY_CODE'], {}).get('flatrate', [])
        if services := {p.get('provider_name', p.get('name')) for p in providers if p.get('provider_id', p.get('id')) in SUBSCRIBED_PROVIDER_IDS}:
            return {'status': 'available_on_streaming', 'message': get_text('status_streaming').format(title=title, services=', '.join(sorted(services)))}
    return {'status': 'not_available', 'title': title}

def add_to_service(service: str, tmdb_id: int, title: str):
    is_radarr = service == 'radarr'
    conf = {k.replace(f'{service.upper()}_', ''): v for k, v in CONFIG.items() if k.startswith(service.upper())}
    headers = {'X-Api-Key': conf['API_KEY']}
    lookup_endpoint = 'movie/lookup/tmdb' if is_radarr else 'series/lookup'
    media_data = api_request('get', f"{conf['URL']}/api/v3/{lookup_endpoint}", headers=headers, params={'tmdbId': tmdb_id} if is_radarr else {'term': f'tmdb:{tmdb_id}'})
    if not media_data: return get_text('add_lookup_fail').format(title=title, service=service.title())
    media_data = media_data if is_radarr else media_data[0]
    title = media_data.get('title', title)
    media_data.update({'qualityProfileId': int(conf['QUALITY_PROFILE_ID']), 'rootFolderPath': conf['ROOT_FOLDER_PATH'], 'monitored': True,
                       'addOptions': {'searchForMovie': True} if is_radarr else {'searchForMissingEpisodes': True, 'monitor': 'all'}})
    response = api_request('post', f"{conf['URL']}/api/v3/{'movie' if is_radarr else 'series'}", headers=headers, json=media_data)
    if isinstance(response, dict) and 'title' in response: return get_text('add_success').format(title=title, service=service.title())
    if isinstance(response, list) and 'already been added' in response[0].get('errorMessage', ''): return get_text('add_exists').format(title=title, service=service.title())
    return get_text('add_fail').format(title=title, service=service.title())

def clear_search_data(context: CallbackContext):
    """Limpa apenas os dados de busca do contexto do usuário, preservando o login."""
    for key in ['search_results', 'search_index', 'search_media_type', 'search_message_id']:
        context.user_data.pop(key, None)

# --- Handlers ---
def start(update: Update, context: CallbackContext): update.message.reply_text(get_text('start_msg', 'en' if not CONFIG else CONFIG.get('LANGUAGE')))

def login_command(update: Update, context: CallbackContext):
    if context.user_data.get('is_logged_in'):
        update.message.reply_text(get_text('already_logged_in'))
        return ConversationHandler.END
    update.message.reply_text(get_text('login_prompt_user', 'en'))
    return GET_USERNAME

def get_username_for_login(update: Update, context: CallbackContext):
    context.user_data['login_user_attempt'] = update.message.text.strip()
    update.message.reply_text(get_text('login_prompt_pass', 'en'))
    return GET_PASSWORD

def check_password(update: Update, context: CallbackContext):
    user = context.user_data.pop('login_user_attempt', None)
    password = update.message.text.strip()
    if user == BOT_USER and password == BOT_PASSWORD:
        context.user_data['is_logged_in'] = True
        update.message.reply_text(get_text('login_success'))
    else:
        update.message.reply_text(get_text('login_fail'))
    return ConversationHandler.END

@check_login
def logout(update: Update, context: CallbackContext):
    context.user_data.clear()
    update.message.reply_text(get_text('logout_success'))

@check_login
def help_command(update: Update, context: CallbackContext): update.message.reply_text(get_text('help_text'))

@check_login
def streaming_command(update: Update, context: CallbackContext):
    text = get_text('streaming_help') + "\n".join([f"`{code}`: {name}" for code, name in PROVIDER_MAP.items()])
    update.message.reply_text(text, parse_mode='Markdown')

@check_login
def language_command(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("🇬🇧 English", callback_data='lang_en'),
                 InlineKeyboardButton("🇧🇷 Português", callback_data='lang_pt'),
                 InlineKeyboardButton("🇪🇸 Español", callback_data='lang_es')]]
    update.message.reply_text(get_text('language_prompt'), reply_markup=InlineKeyboardMarkup(keyboard))

def set_language(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    lang_code = query.data.split('_')[1]
    CONFIG['LANGUAGE'] = lang_code
    save_config()
    lang_name = {"en": "English", "pt": "Português", "es": "Español"}.get(lang_code)
    query.edit_message_text(text=get_text('language_set', lang=lang_code).format(lang=lang_name))

@check_login
def setup(update: Update, context: CallbackContext) -> int:
    context.user_data['setup_data'] = {}
    update.message.reply_text(get_text('setup_welcome', 'en'))
    return GET_RADARR_URL

def get_text_and_move(update, context, key, prompt_key, next_state):
    context.user_data['setup_data'][key] = update.message.text.strip()
    update.message.reply_text(get_text(prompt_key, 'en'))
    return next_state

def skip_radarr(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(get_text('setup_skip_radarr', 'en'))
    for key in ['RADARR_URL', 'RADARR_API_KEY', 'RADARR_QUALITY_PROFILE_ID', 'RADARR_ROOT_FOLDER_PATH']:
        context.user_data['setup_data'][key] = ""
    update.message.reply_text(get_text('setup_sonarr_url', 'en'))
    return GET_SONARR_URL

def skip_sonarr(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(get_text('setup_skip_sonarr', 'en'))
    for key in ['SONARR_URL', 'SONARR_API_KEY', 'SONARR_QUALITY_PROFILE_ID', 'SONARR_ROOT_FOLDER_PATH']:
        context.user_data['setup_data'][key] = ""
    update.message.reply_text(get_text('setup_overseerr_url', 'en'))
    return GET_OVERSEERR_URL

def get_country_code(update: Update, context: CallbackContext):
    context.user_data['setup_data']['JUSTWATCH_COUNTRY_CODE'] = update.message.text.strip().upper()
    context.user_data['setup_data']['LANGUAGE'] = CONFIG.get('LANGUAGE', 'en')
    update.message.reply_text(get_text('setup_finished', 'en'))
    save_config(new_config=context.user_data.pop('setup_data'))
    update.message.reply_text(get_text('setup_success', 'en'))
    return ConversationHandler.END

def cancel_setup(update: Update, context: CallbackContext):
    lang = context.user_data.get('setup_data', {}).get('LANGUAGE', CONFIG.get('LANGUAGE', 'en'))
    update.message.reply_text(get_text('setup_canceled', lang))
    context.user_data.pop('setup_data', None)
    return ConversationHandler.END

@check_config
@check_login
def search_media(update: Update, context: CallbackContext, media_type: str):
    if media_type == 'movie' and not CONFIG.get('RADARR_URL'): return update.message.reply_text(get_text('radarr_not_configured'))
    if media_type == 'show' and not CONFIG.get('SONARR_URL'): return update.message.reply_text(get_text('sonarr_not_configured'))
    query_str = ' '.join(context.args)
    if not query_str: return update.message.reply_text(get_text('usage_tip').format(command=media_type))
    msg = update.message.reply_text(get_text('searching').format(query=query_str))
    results = search_radarr(query_str) if media_type == 'movie' else search_sonarr(query_str)
    msg.delete()
    if not results: return update.message.reply_text(get_text('no_results').format(query=query_str))
    clear_search_data(context)
    context.user_data.update({'search_results': results, 'search_index': 0, 'search_media_type': media_type})
    display_search_result(update, context)

def display_search_result(update: Update, context: CallbackContext):
    query = update.callback_query
    results, index, media_type = (context.user_data.get(k) for k in ['search_results', 'search_index', 'search_media_type'])
    item = results[index]
    title, year, tmdb_id = item.get('title'), item.get('year'), item.get('tmdbId')
    overview = (item.get('overview') or get_text('no_overview'))
    if len(overview) > 700: overview = overview[:700] + '...'
    poster_path = next((img.get('remoteUrl') or img.get('url') for img in item.get('images', []) if img.get('coverType') == 'poster'), None)
    poster_url = poster_path if poster_path and poster_path.startswith('http') else f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else f"https://placehold.co/500x750/1c1c1e/ffffff?text={requests.utils.quote(title or 'No Title')}"
    caption = f"*{title} ({year})*\n\n{overview}"
    nav_row = [
        InlineKeyboardButton("⬅️ Prev" if index > 0 else " ", callback_data="nav_prev" if index > 0 else "noop"),
        InlineKeyboardButton("ℹ️ TMDB", url=f"https://www.themoviedb.org/{'movie' if media_type == 'movie' else 'tv'}/{tmdb_id}"),
        InlineKeyboardButton("Next ➡️" if index < len(results) - 1 else " ", callback_data="nav_next" if index < len(results) - 1 else "noop")
    ]
    add_btn_text = get_text('add_movie_btn' if media_type == 'movie' else 'add_show_btn')
    reply_markup = InlineKeyboardMarkup([[*nav_row], [InlineKeyboardButton(add_btn_text, callback_data=f"add_{media_type}_{tmdb_id}")], [InlineKeyboardButton(get_text('cancel_btn'), callback_data="nav_cancel")]])
    media = InputMediaPhoto(media=poster_url, caption=caption, parse_mode='Markdown')
    effective_message = query.message if query else update.message
    if query:
        try: query.edit_message_media(media=media, reply_markup=reply_markup)
        except Exception as e:
            if 'Message is not modified' not in str(e): logger.warning(f"Erro ao editar mídia: {e}")
    else:
        message = effective_message.reply_photo(photo=poster_url, caption=caption, reply_markup=reply_markup, parse_mode='Markdown')
        context.user_data['search_message_id'] = message.message_id

@check_config
@check_login
def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query; query.answer()
    action, *payload = query.data.split('_')
    if action == "noop": return
    if action == "nav":
        if payload[0] == "cancel": 
            query.delete_message()
            clear_search_data(context)
            return
        context.user_data['search_index'] += 1 if payload[0] == "next" else -1
        display_search_result(update, context); return
    if action == "lang":
        set_language(update, context); return
    
    media_type, tmdb_id = payload[0], int(payload[1])

    if media_type == 'movie' and not CONFIG.get('RADARR_URL'): return query.message.reply_text(get_text('radarr_not_configured'))
    if media_type == 'show' and not CONFIG.get('SONARR_URL'): return query.message.reply_text(get_text('sonarr_not_configured'))

    query.delete_message()
    clear_search_data(context)
    status_msg = query.message.reply_text(get_text('status_checking'))
    status_check = get_overseerr_status_by_id(tmdb_id, media_type)
    if (status := status_check.get('status')) in ['available_on_server', 'pending_on_server', 'available_on_streaming', 'error']:
        final_message = status_check.get('message')
    elif status == 'not_available':
        title = status_check.get('title', 'mídia')
        status_msg.edit_text(get_text('status_adding').format(title=title))
        final_message = add_to_service('radarr' if media_type == 'movie' else 'sonarr', tmdb_id, title)
    else: final_message = get_text('unexpected_error')
    status_msg.edit_text(final_message)

def main():
    if not all([BOT_TOKEN, BOT_USER, BOT_PASSWORD]):
        logger.critical("!!! BOT_TOKEN, BOT_USER, e BOT_PASSWORD são necessários.")
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

    setup_states = {
        GET_RADARR_URL: (lambda u,c: get_text_and_move(u,c,'RADARR_URL','setup_radarr_api',GET_RADARR_API)),
        GET_RADARR_API: (lambda u,c: get_text_and_move(u,c,'RADARR_API_KEY','setup_radarr_quality',GET_RADARR_QUALITY)),
        GET_RADARR_QUALITY: (lambda u,c: get_text_and_move(u,c,'RADARR_QUALITY_PROFILE_ID','setup_radarr_path',GET_RADARR_PATH)),
        GET_RADARR_PATH: (lambda u,c: get_text_and_move(u,c,'RADARR_ROOT_FOLDER_PATH','setup_sonarr_url',GET_SONARR_URL)),
    }
    sonarr_states = {
        GET_SONARR_URL: (lambda u,c: get_text_and_move(u,c,'SONARR_URL','setup_sonarr_api',GET_SONARR_API)),
        GET_SONARR_API: (lambda u,c: get_text_and_move(u,c,'SONARR_API_KEY','setup_sonarr_quality',GET_SONARR_QUALITY)),
        GET_SONARR_QUALITY: (lambda u,c: get_text_and_move(u,c,'SONARR_QUALITY_PROFILE_ID','setup_sonarr_path',GET_SONARR_PATH)),
        GET_SONARR_PATH: (lambda u,c: get_text_and_move(u,c,'SONARR_ROOT_FOLDER_PATH','setup_overseerr_url',GET_OVERSEERR_URL)),
    }
    overseerr_states = {
        GET_OVERSEERR_URL: (lambda u,c: get_text_and_move(u,c,'OVERSEERR_URL','setup_overseerr_api',GET_OVERSEERR_API)),
        GET_OVERSEERR_API: (lambda u,c: get_text_and_move(u,c,'OVERSEERR_API_KEY','setup_streaming',GET_STREAMING_SERVICES)),
        GET_STREAMING_SERVICES: (lambda u,c: get_text_and_move(u,c,'SUBSCRIBED_SERVICES_CODES', 'setup_country', GET_COUNTRY_CODE)),
        GET_COUNTRY_CODE: get_country_code
    }

    setup_conv = ConversationHandler(
        entry_points=[CommandHandler('setup', setup)],
        states={
            **{state: [MessageHandler(Filters.text & ~Filters.command, func), CommandHandler('skip', skip_radarr)] for state, func in setup_states.items()},
            **{state: [MessageHandler(Filters.text & ~Filters.command, func), CommandHandler('skip', skip_sonarr)] for state, func in sonarr_states.items()},
            **{state: [MessageHandler(Filters.text & ~Filters.command, func)] for state, func in overseerr_states.items()},
        },
        fallbacks=[CommandHandler('cancel', cancel_setup)]
    )
    
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(login_conv)
    dispatcher.add_handler(CommandHandler("logout", logout))
    dispatcher.add_handler(setup_conv)
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("streaming", streaming_command))
    dispatcher.add_handler(CommandHandler("language", language_command))
    dispatcher.add_handler(CommandHandler("movie", lambda u,c: search_media(u,c,'movie')))
    dispatcher.add_handler(CommandHandler("show", lambda u,c: search_media(u,c,'show')))
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    
    load_config()
    logger.info("Bot iniciado e escutando...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    try: main()
    except Exception as e: logger.critical(f"O bot encontrou um erro fatal: {e}", exc_info=True); sys.exit(1)

