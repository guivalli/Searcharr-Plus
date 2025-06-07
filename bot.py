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

# Logger
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file = 'logs/bot.log'
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2)
file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# --- Gerenciamento de Configuração e Idioma ---
CONFIG_FILE = 'config/config.json'
CONFIG = {}
BOT_TOKEN = os.getenv('BOT_TOKEN')
SUBSCRIBED_PROVIDER_IDS = set()

# Dicionário de Traduções
translations = {
    'en': {
        "start_msg": "Hello! Use /movie <name> or /show <name> to search.\nUse /setup to (re)configure the bot and /language to change the language.",
        "help_text": (
            "Here are the available commands:\n"
            "/start - Check if the bot is running.\n"
            "/movie <name> - Search for a movie.\n"
            "/show <name> - Search for a series.\n"
            "/setup - Start the guided configuration process.\n"
            "/language - Change the bot's language.\n"
            "/streaming - List available streaming service codes.\n"
            "/help - Show this help message."
        ),
        "streaming_help": "Here are the available streaming service codes for configuration:\n",
        "setup_needed": "The bot needs to be configured first. Use /setup.",
        "setup_welcome": "Hello! Let's set up the bot.\nUse /cancel to stop or /skip to skip a section (Radarr/Sonarr).\n\nWhat is the full URL of your Radarr (e.g., http://192.168.1.10:7878)?",
        "setup_skip_radarr": "Skipping Radarr setup.",
        "setup_skip_sonarr": "Skipping Sonarr setup.",
        "radarr_not_configured": "Radarr is not configured. Use /setup to add it.",
        "sonarr_not_configured": "Sonarr is not configured. Use /setup to add it.",
        "setup_radarr_api": "Got it. Now, what is the Radarr API Key?",
        "setup_radarr_quality": "What is the Radarr Quality Profile ID?",
        "setup_radarr_path": "And what is the Radarr Root Folder Path (e.g., /movies/)?",
        "setup_sonarr_url": "Perfect. Now for Sonarr. What is the full Sonarr URL?",
        "setup_sonarr_api": "Got it. And the Sonarr API Key?",
        "setup_sonarr_quality": "What is the Sonarr Quality Profile ID?",
        "setup_sonarr_path": "What is the Sonarr Root Folder Path (e.g., /tv/)?",
        "setup_overseerr_url": "Almost there! What is your Overseerr's full URL?",
        "setup_overseerr_api": "And the Overseerr API Key?",
        "setup_streaming": "Now, enter the codes for your streaming services, separated by commas (e.g., nfx,amp,max). Use /streaming to see all options.",
        "setup_country": "Last question: What is your country code for JustWatch (e.g., US, GB, BR)?",
        "setup_finished": "Excellent! Saving configuration...",
        "setup_success": "✅ Configuration saved! The bot is ready to use. You can change the language with /language.",
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
    },
    'pt': {
        "start_msg": "Olá! Use /movie <nome> ou /show <nome> para buscar.\nUse /setup para (re)configurar o bot e /language para mudar o idioma.",
        "help_text": (
            "Aqui estão os comandos disponíveis:\n"
            "/start - Verifica se o bot está funcionando.\n"
            "/movie <nome> - Procura por um filme.\n"
            "/show <nome> - Procura por uma série.\n"
            "/setup - Inicia o processo de configuração guiada.\n"
            "/language - Altera o idioma do bot.\n"
            "/streaming - Lista os códigos de serviços de streaming disponíveis.\n"
            "/help - Mostra esta mensagem de ajuda."
        ),
        "streaming_help": "Aqui estão os códigos de serviços de streaming disponíveis para a configuração:\n",
        "setup_needed": "O bot precisa ser configurado primeiro. Use /setup.",
        "setup_welcome": "Olá! Vamos configurar o bot.\nUse /cancel para parar ou /skip para pular uma seção (Radarr/Sonarr).\n\nQual a URL completa do seu Radarr (ex: http://192.168.1.10:7878)?",
        "setup_skip_radarr": "Pulando configuração do Radarr.",
        "setup_skip_sonarr": "Pulando configuração do Sonarr.",
        "radarr_not_configured": "O Radarr não está configurado. Use /setup para adicioná-lo.",
        "sonarr_not_configured": "O Sonarr não está configurado. Use /setup para adicioná-lo.",
        "setup_radarr_api": "Ok. Agora, qual a Chave de API (API Key) do Radarr?",
        "setup_radarr_quality": "Qual o ID do Perfil de Qualidade (Quality Profile ID) do Radarr?",
        "setup_radarr_path": "E qual o Caminho da Pasta Raiz (Root Folder Path) do Radarr (ex: /movies/)?",
        "setup_sonarr_url": "Perfeito. Agora para o Sonarr. Qual a URL completa do Sonarr?",
        "setup_sonarr_api": "Ok. E a Chave de API (API Key) do Sonarr?",
        "setup_sonarr_quality": "Qual o ID do Perfil de Qualidade (Quality Profile ID) do Sonarr?",
        "setup_sonarr_path": "Qual o Caminho da Pasta Raiz (Root Folder Path) do Sonarr (ex: /tv/)?",
        "setup_overseerr_url": "Quase lá! Qual a URL completa do seu Overseerr?",
        "setup_overseerr_api": "E a Chave de API (API Key) do Overseerr?",
        "setup_streaming": "Agora, informe os códigos dos seus serviços de streaming, separados por vírgula (ex: nfx,amp,max). Use /streaming para ver todas as opções.",
        "setup_country": "Última pergunta: Qual o código do seu país para o JustWatch (ex: BR, US, PT)?",
        "setup_finished": "Excelente! Salvando configuração...",
        "setup_success": "✅ Configuração salva! O bot está pronto para ser usado. Você pode mudar o idioma com /language.",
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
    },
    'es': {
        "start_msg": "¡Hola! Usa /movie <nombre> o /show <nombre> para buscar.\nUsa /setup para (re)configurar el bot y /language para cambiar el idioma.",
        "help_text": (
            "Aquí están los comandos disponibles:\n"
            "/start - Comprueba si el bot está funcionando.\n"
            "/movie <nombre> - Busca una película.\n"
            "/show <nombre> - Busca una serie.\n"
            "/setup - Inicia el proceso de configuración guiada.\n"
            "/language - Cambia el idioma del bot.\n"
            "/streaming - Lista los códigos de servicios de streaming disponibles.\n"
            "/help - Muestra este mensaje de ayuda."
        ),
        "streaming_help": "Aquí están los códigos de servicios de streaming disponibles para la configuración:\n",
        "setup_needed": "El bot necesita ser configurado primero. Usa /setup.",
        "setup_welcome": "¡Hola! Vamos a configurar el bot.\nUsa /cancel para detenerte o /skip para saltar una sección (Radarr/Sonarr).\n\n¿Cuál es la URL completa de tu Radarr (ej: http://192.168.1.10:7878)?",
        "setup_skip_radarr": "Saltando configuración de Radarr.",
        "setup_skip_sonarr": "Saltando configuración de Sonarr.",
        "radarr_not_configured": "Radarr no está configurado. Usa /setup para agregarlo.",
        "sonarr_not_configured": "Sonarr no está configurado. Usa /setup para agregarlo.",
        "setup_radarr_api": "Entendido. Ahora, ¿cuál es la Clave de API (API Key) de Radarr?",
        "setup_radarr_quality": "¿Cuál es el ID del Perfil de Calidad (Quality Profile ID) de Radarr?",
        "setup_radarr_path": "¿Y cuál es la Ruta de la Carpeta Raíz (Root Folder Path) de Radarr (ej: /movies/)?",
        "setup_sonarr_url": "Perfecto. Ahora para Sonarr. ¿Cuál es la URL completa de Sonarr?",
        "setup_sonarr_api": "Entendido. ¿Y la Clave de API (API Key) de Sonarr?",
        "setup_sonarr_quality": "¿Cuál es el ID del Perfil de Calidad (Quality Profile ID) de Sonarr?",
        "setup_sonarr_path": "¿Cuál es la Ruta de la Carpeta Raíz (Root Folder Path) de Sonarr (ej: /tv/)?",
        "setup_overseerr_url": "¡Casi listo! ¿Cuál es la URL completa de tu Overseerr?",
        "setup_overseerr_api": "¿Y la Clave de API (API Key) de Overseerr?",
        "setup_streaming": "Ahora, introduce los códigos de tus servicios de streaming, separados por comas (ej: nfx,amp,max). Usa /streaming para ver todas las opciones.",
        "setup_country": "Última pregunta: ¿Cuál es el código de tu país para JustWatch (ej: ES, MX, US)?",
        "setup_finished": "¡Excelente! Guardando configuración...",
        "setup_success": "✅ ¡Configuración guardada! El bot está listo para usarse. Puedes cambiar el idioma con /language.",
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
    }
}

def get_text(key, lang=None):
    if lang is None: lang = CONFIG.get('LANGUAGE', 'en')
    return translations.get(lang, translations['en']).get(key, f"_{key}_")

(GET_RADARR_URL, GET_RADARR_API, GET_RADARR_QUALITY, GET_RADARR_PATH,
 GET_SONARR_URL, GET_SONARR_API, GET_SONARR_QUALITY, GET_SONARR_PATH,
 GET_OVERSEERR_URL, GET_OVERSEERR_API, GET_STREAMING_SERVICES, GET_COUNTRY_CODE) = range(12)

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

def check_config(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if not CONFIG:
            if update.callback_query: update.callback_query.answer(get_text('setup_needed'), show_alert=True)
            elif update.message: update.message.reply_text(get_text('setup_needed'))
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

# --- Handlers ---
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
    context.user_data['setup_data']['LANGUAGE'] = 'en'
    update.message.reply_text(get_text('setup_finished', 'en'))
    save_config(new_config=context.user_data.pop('setup_data'))
    update.message.reply_text(get_text('setup_success', 'en'))
    return ConversationHandler.END

def cancel_setup(update: Update, context: CallbackContext):
    lang = context.user_data.get('setup_data', {}).get('LANGUAGE', CONFIG.get('LANGUAGE', 'en'))
    update.message.reply_text(get_text('setup_canceled', lang))
    context.user_data.pop('setup_data', None)
    return ConversationHandler.END

def start(update: Update, context: CallbackContext): update.message.reply_text(get_text('start_msg'))
def help_command(update: Update, context: CallbackContext): update.message.reply_text(get_text('help_text'))
def streaming_command(update: Update, context: CallbackContext):
    text = get_text('streaming_help') + "\n".join([f"`{code}`: {name}" for code, name in PROVIDER_MAP.items()])
    update.message.reply_text(text, parse_mode='Markdown')

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

@check_config
def search_media(update: Update, context: CallbackContext, media_type: str):
    if media_type == 'movie' and not CONFIG.get('RADARR_URL'): return update.message.reply_text(get_text('radarr_not_configured'))
    if media_type == 'show' and not CONFIG.get('SONARR_URL'): return update.message.reply_text(get_text('sonarr_not_configured'))

    query_str = ' '.join(context.args)
    if not query_str: return update.message.reply_text(get_text('usage_tip').format(command=media_type))
    msg = update.message.reply_text(get_text('searching').format(query=query_str))
    results = search_radarr(query_str) if media_type == 'movie' else search_sonarr(query_str)
    msg.delete()
    if not results: return update.message.reply_text(get_text('no_results').format(query=query_str))
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
    if query:
        try: query.edit_message_media(media=media, reply_markup=reply_markup)
        except Exception as e:
            if 'Message is not modified' not in str(e): logger.warning(f"Erro ao editar mídia: {e}")
    else:
        message = (update.message or update.effective_message).reply_photo(photo=poster_url, caption=caption, reply_markup=reply_markup, parse_mode='Markdown')
        context.user_data['search_message_id'] = message.message_id

@check_config
def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query; query.answer()
    action, *payload = query.data.split('_')
    if action == "noop": return
    if action == "nav":
        if payload[0] == "cancel": query.delete_message(); context.user_data.clear(); return
        context.user_data['search_index'] += 1 if payload[0] == "next" else -1
        display_search_result(update, context); return
    if action == "lang":
        set_language(update, context); return
    
    media_type, tmdb_id = payload[0], int(payload[1])

    if media_type == 'movie' and not CONFIG.get('RADARR_URL'): return query.message.reply_text(get_text('radarr_not_configured'))
    if media_type == 'show' and not CONFIG.get('SONARR_URL'): return query.message.reply_text(get_text('sonarr_not_configured'))

    query.delete_message(); context.user_data.clear()
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
    if not BOT_TOKEN: return logger.critical("!!! BOT_TOKEN não encontrado.")
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher
    
    radarr_states = {
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

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setup', setup)],
        states={
            **{state: [MessageHandler(Filters.text & ~Filters.command, func), CommandHandler('skip', skip_radarr)] for state, func in radarr_states.items()},
            **{state: [MessageHandler(Filters.text & ~Filters.command, func), CommandHandler('skip', skip_sonarr)] for state, func in sonarr_states.items()},
            **{state: [MessageHandler(Filters.text & ~Filters.command, func)] for state, func in overseerr_states.items()},
        },
        fallbacks=[CommandHandler('cancel', cancel_setup)]
    )
    
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler("start", start))
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
