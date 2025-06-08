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
    from plexapi.myplex import MyPlexAccount
    from plexapi.exceptions import Unauthorized, NotFound
    PLEX_AVAILABLE = True
except ImportError:
    PLEX_AVAILABLE = False


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

# Estados da conversa
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


# Dicionário de Traduções (COMPLETO)
translations = {
    'en': {
        "start_msg": "Hello! Please /login (admin) or /auth <code> (friend) to use the bot.",
        "help_admin": "Admin Commands:\n/start - Welcome\n/login - Authenticate\n/logout - End session\n/movie <name> - Search movie\n/show <name> - Search series\n/setup - Guided configuration\n/language - Change language\n/streaming - List codes\n/friends - Manage friend access\n/debug <movie|show> <name> - Debug media checks\n/help - This message",
        "help_friend": "Available Commands:\n/movie <name> - Check if a movie is available\n/show <name> - Check if a series is available\n/logout - End your session",
        "friends_help": "Manage friend access:\n/friends add <name> - Create an access code for a friend.\n/friends remove <name> - Revoke a friend's access.\n/friends list - List all friends and their codes.",
        "friend_added": "✅ Friend '{name}' added. Their access code is: `{code}`\nPlease share it with them securely.",
        "friend_removed": "✅ Friend '{name}' has been removed.",
        "friend_list_title": "Friend List:",
        "friend_not_found": "❌ Friend '{name}' not found.",
        "no_friends": "You have not added any friends yet.",
        "auth_prompt": "Please provide your access code. Usage: /auth <your_code>",
        "auth_success": "✅ Friend access granted! Welcome. Use /movie or /show to check for media.",
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
        "setup_needed": "Bot needs to be configured. Use /setup.",
        "setup_welcome": "Hello! Let's set up the bot.\nUse /cancel to stop or /skip to skip a section (Radarr/Sonarr).\n\nWhat is the full URL of your Radarr (e.g., http://192.168.1.10:7878)?",
        "setup_skip_radarr": "Skipping Radarr setup.",
        "setup_skip_sonarr": "Skipping Sonarr setup.",
        "setup_skip_plex": "Skipping Plex setup.",
        "setup_skip_tmdb": "Skipping TMDB & Region setup.",
        "setup_skip_overseerr": "Skipping Overseerr setup.",
        "setup_skip_streaming": "Skipping streaming services.",
        "radarr_not_configured": "Radarr is not configured. Use /setup to add it.",
        "sonarr_not_configured": "Sonarr is not configured. Use /setup to add it.",
        "setup_radarr_api": "Got it. Radarr API Key?",
        "setup_radarr_quality": "Radarr Quality Profile ID?",
        "setup_radarr_path": "Radarr Root Folder Path (e.g., /movies/)?",
        "setup_sonarr_url": "Perfect. Now, Sonarr's full URL?",
        "setup_sonarr_api": "Got it. Sonarr API Key?",
        "setup_sonarr_quality": "Sonarr Quality Profile ID?",
        "setup_sonarr_path": "Sonarr Root Folder Path (e.g., /tv/)?",
        "setup_plex_token": "Great. Please provide your Plex Authentication Token.",
        "setup_plex_url": "Please enter the full URL of your main Plex server (e.g., http://192.168.1.12:32400).",
        "setup_tmdb_api": "Excellent. Now, please provide your TMDB API Key (v3 Auth). This is required for checking streaming providers.",
        "setup_region": "Great. Now, please enter the two-letter country code for your primary streaming region (e.g., BR for Brazil, US for United States). This will be used to check for streaming availability.",
        "setup_ask_overseerr": "Plex is configured. Do you also want to add Overseerr to check for pending requests? (yes/no)",
        "setup_overseerr_url": "Got it. Overseerr's full URL?",
        "setup_overseerr_api": "And the Overseerr API Key?",
        "setup_streaming": "Enter your streaming service codes, comma-separated (e.g., nfx,amp,max). Use /streaming for options.",
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
        "plex_found": "✅ '{title}' is already available on your Plex server: {server_name}.",
        "plex_not_available": "Plex integration is not available because the `plexapi` library is not installed.",
        "tmdb_not_configured": "TMDB API Key is not configured. Use /setup.",
        "checking_tmdb": "Checking TMDB for streaming options...",
    },
    'pt': {
        "start_msg": "Olá! Por favor, use /login (admin) ou /auth <código> (amigo) para usar o bot.",
        "help_admin": "Comandos de Admin:\n/start - Boas-vindas\n/login - Autenticar\n/logout - Encerrar sessão\n/movie <nome> - Procurar filme\n/show <nome> - Procurar série\n/setup - Configuração guiada\n/language - Mudar idioma\n/streaming - Listar códigos\n/friends - Gerenciar acesso de amigos\n/debug <movie|show> <nome> - Depurar checagem de mídia\n/help - Esta mensagem",
        "help_friend": "Comandos Disponíveis:\n/movie <nome> - Verificar se um filme está disponível\n/show <nome> - Verificar se uma série está disponível\n/logout - Encerrar sua sessão",
        "friends_help": "Gerenciar acesso de amigos:\n/friends add <nome> - Cria um código de acesso para um amigo.\n/friends remove <nome> - Revoga o acesso de um amigo.\n/friends list - Lista todos os amigos e seus códigos.",
        "friend_added": "✅ Amigo '{name}' adicionado. O código de acesso dele é: `{code}`\nPor favor, compartilhe com ele de forma segura.",
        "friend_removed": "✅ Amigo '{name}' foi removido.",
        "friend_list_title": "Lista de Amigos:",
        "friend_not_found": "❌ Amigo '{name}' não encontrado.",
        "no_friends": "Você ainda não adicionou nenhum amigo.",
        "auth_prompt": "Por favor, forneça seu código de acesso. Uso: /auth <seu_código>",
        "auth_success": "✅ Acesso de amigo concedido! Bem-vindo. Use /movie ou /show para consultar a biblioteca.",
        "auth_fail": "❌ Código de acesso inválido.",
        "not_available_friend": "Desculpe, '{title}' ainda não está disponível na biblioteca.",
        "login_prompt_user": "Por favor, digite seu nome de usuário de admin.",
        "login_prompt_pass": "Por favor, digite sua senha.",
        "login_success": "✅ Login de admin realizado com sucesso! Use /help para ver os comandos.",
        "login_fail": "❌ Credenciais inválidas. Tente /login novamente.",
        "login_needed": "Você precisa estar logado. Por favor, use /login ou /auth.",
        "logout_success": "Você foi desconectado.",
        "already_logged_in": "Você já está logado.",
        "admin_only": "❌ Este comando é apenas para admins.",
        "streaming_help": "Códigos de serviços de streaming disponíveis para a configuração:\n",
        "setup_needed": "O bot precisa ser configurado. Use /setup.",
        "setup_welcome": "Olá! Vamos configurar o bot.\nUse /cancel para parar ou /skip para pular uma seção (Radarr/Sonarr).\n\nQual a URL completa do seu Radarr (ex: http://192.168.1.10:7878)?",
        "setup_skip_radarr": "Pulando configuração do Radarr.",
        "setup_skip_sonarr": "Pulando configuração do Sonarr.",
        "setup_skip_plex": "Pulando configuração do Plex.",
        "setup_skip_tmdb": "Pulando configuração do TMDB e Região.",
        "setup_skip_overseerr": "Pulando configuração do Overseerr.",
        "setup_skip_streaming": "Pulando configuração dos serviços de streaming.",
        "radarr_not_configured": "O Radarr não está configurado. Use /setup para adicioná-lo.",
        "sonarr_not_configured": "O Sonarr não está configurado. Use /setup para adicioná-lo.",
        "setup_radarr_api": "Ok. Chave de API (API Key) do Radarr?",
        "setup_radarr_quality": "ID do Perfil de Qualidade do Radarr?",
        "setup_radarr_path": "Caminho da Pasta Raiz do Radarr (ex: /movies/)?",
        "setup_sonarr_url": "Perfeito. Agora, a URL completa do Sonarr?",
        "setup_sonarr_api": "Ok. Chave de API (API Key) do Sonarr?",
        "setup_sonarr_quality": "ID do Perfil de Qualidade do Sonarr?",
        "setup_sonarr_path": "Caminho da Pasta Raiz do Sonarr (ex: /tv/)?",
        "setup_plex_token": "Ótimo. Por favor, forneça seu Token de Autenticação do Plex.",
        "setup_plex_url": "Por favor, digite a URL completa do seu servidor Plex principal (ex: http://192.168.1.12:32400).",
        "setup_tmdb_api": "Excelente. Agora, por favor, forneça sua chave de API do TMDB (v3 Auth). Ela é necessária para verificar os provedores de streaming.",
        "setup_region": "Ótimo. Agora, por favor, insira o código de duas letras do seu país para a região de streaming (ex: BR para Brasil, US para Estados Unidos). Isso será usado para verificar a disponibilidade em streamings.",
        "setup_ask_overseerr": "Plex configurado. Você também deseja adicionar o Overseerr para verificar pedidos pendentes? (sim/não)",
        "setup_overseerr_url": "Ok. URL completa do Overseerr?",
        "setup_overseerr_api": "E a Chave de API do Overseerr?",
        "setup_streaming": "Informe os códigos dos seus serviços de streaming, separados por vírgula (ex: nfx,amp,max). Use /streaming para opções.",
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
        "plex_found": "✅ '{title}' já está disponível no seu servidor Plex: {server_name}.",
        "plex_not_available": "A integração com o Plex não está disponível porque a biblioteca `plexapi` não foi instalada.",
        "tmdb_not_configured": "A chave de API do TMDB não está configurada. Use /setup.",
        "checking_tmdb": "Verificando o TMDB para opções de streaming...",
    },
    'es': {
        "start_msg": "¡Hola! Por favor, usa /login (admin) o /auth <código> (amigo) para usar el bot.",
        "help_admin": "Comandos de Admin:\n/start - Bienvenida\n/login - Autenticarse\n/logout - Cerrar sesión\n/movie <nombre> - Buscar película\n/show <nombre> - Buscar serie\n/setup - Configuración guiada\n/language - Cambiar idioma\n/streaming - Listar códigos\n/friends - Gestionar acceso de amigos\n/debug <movie|show> <nombre> - Depurar comprobaciones de medios\n/help - Este mensaje",
        "help_friend": "Comandos Disponibles:\n/movie <nombre> - Consultar si una película está disponible\n/show <nombre> - Consultar si una serie está disponible\n/logout - Cerrar tu sesión",
        "friends_help": "Gestionar acceso de amigos:\n/friends add <nombre> - Crea un código de acceso para un amigo.\n/friends remove <nombre> - Revoca el acceso de un amigo.\n/friends list - Lista todos los amigos y sus códigos.",
        "friend_added": "✅ Amigo '{name}' añadido. Su código de acceso es: `{code}`\nPor favor, compártelo con él de forma segura.",
        "friend_removed": "✅ Amigo '{name}' ha sido eliminado.",
        "friend_list_title": "Lista de Amigos:",
        "friend_not_found": "❌ Amigo '{name}' no encontrado.",
        "no_friends": "Aún no has añadido ningún amigo.",
        "auth_prompt": "Por favor, proporciona tu código de acceso. Uso: /auth <tu_código>",
        "auth_success": "✅ ¡Acceso de amigo concedido! Bienvenido. Usa /movie o /show para consultar la biblioteca.",
        "auth_fail": "❌ Código de acceso inválido.",
        "not_available_friend": "Lo siento, '{title}' aún no está disponible en la biblioteca.",
        "login_prompt_user": "Por favor, introduce tu nombre de usuario de admin.",
        "login_prompt_pass": "Por favor, introduce tu contraseña.",
        "login_success": "✅ ¡Inicio de sesión de admin exitoso! Usa /help para ver los comandos.",
        "login_fail": "❌ Credenciales inválidas. Intenta /login de nuevo.",
        "login_needed": "Debes iniciar sesión. Por favor, usa /login o /auth.",
        "logout_success": "Has cerrado la sesión.",
        "already_logged_in": "Ya has iniciado sesión.",
        "admin_only": "❌ Este comando es solo para admins.",
        "streaming_help": "Códigos de servicios de streaming disponibles para la configuración:\n",
        "setup_needed": "El bot necesita ser configurado. Usa /setup.",
        "setup_welcome": "¡Hola! Vamos a configurar el bot.\nUsa /cancel para detenerte o /skip para saltar una sección (Radarr/Sonarr).\n\n¿Cuál es la URL completa de tu Radarr (ej: http://192.168.1.10:7878)?",
        "setup_skip_radarr": "Saltando configuración de Radarr.",
        "setup_skip_sonarr": "Saltando configuración de Sonarr.",
        "setup_skip_plex": "Saltando configuración de Plex.",
        "setup_skip_tmdb": "Saltando la configuración de TMDB y Región.",
        "setup_skip_overseerr": "Saltando la configuración de Overseerr.",
        "setup_skip_streaming": "Omitiendo la configuración de los servicios de transmisión.",
        "radarr_not_configured": "Radarr no está configurado. Usa /setup para agregarlo.",
        "sonarr_not_configured": "Sonarr no está configurado. Usa /setup para agregarlo.",
        "setup_radarr_api": "Entendido. ¿Clave de API (API Key) de Radarr?",
        "setup_radarr_quality": "¿ID del Perfil de Calidad de Radarr?",
        "setup_radarr_path": "¿Ruta de la Carpeta Raíz de Radarr (ej: /movies/)?",
        "setup_sonarr_url": "Perfecto. Ahora, ¿URL completa de Sonarr?",
        "setup_sonarr_api": "Entendido. ¿Clave de API (API Key) de Sonarr?",
        "setup_sonarr_quality": "¿ID del Perfil de Calidad de Sonarr?",
        "setup_sonarr_path": "¿Ruta de la Carpeta Raíz de Sonarr (ej: /tv/)?",
        "setup_plex_token": "Genial. Por favor, proporciona tu Token de Autenticación de Plex.",
        "setup_plex_url": "Por favor, introduce la URL completa de tu servidor Plex principal (ej: http://192.168.1.12:32400).",
        "setup_tmdb_api": "Excelente. Ahora, por favor, proporciona tu clave de API de TMDB (v3 Auth). Es necesaria para comprobar los proveedores de streaming.",
        "setup_region": "Estupendo. Ahora, por favor, introduce el código de país de dos letras para tu región principal de streaming (ej: BR para Brasil, US para Estados Unidos). Se utilizará para comprobar la disponibilidad de streaming.",
        "setup_ask_overseerr": "Plex configurado. ¿También quieres añadir Overseerr para comprobar solicitudes pendientes? (si/no)",
        "setup_overseerr_url": "OK. ¿URL completa de Overseerr?",
        "setup_overseerr_api": "¿Y la Clave de API de Overseerr?",
        "setup_streaming": "Introduce los códigos de tus servicios de streaming, separados por comas (ej: nfx,amp,max). Usa /streaming para opciones.",
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
        "plex_found": "✅ '{title}' ya está disponible en tu servidor Plex: {server_name}.",
        "plex_not_available": "La integración con Plex no está disponible porque la biblioteca `plexapi` no está instalada.",
        "tmdb_not_configured": "La clave API de TMDB no está configurada. Utilice /setup.",
        "checking_tmdb": "Comprobando TMDB para opciones de streaming...",
    }
}

def get_text(key, lang=None):
    if lang is None: lang = CONFIG.get('LANGUAGE', 'en')
    return translations.get(lang, translations['en']).get(key, translations['en'].get(key, f"_{key}_"))

PROVIDER_MAP = {
    'nfx': 'Netflix', 'amp': 'Amazon Prime Video', 'max': 'Max', 'glb': 'GloboPlay',
    'pmp': 'Paramount+', 'dnp': 'Disney+', 'apv': 'Apple TV+', 'sp': 'Star+'
}

def load_config():
    global CONFIG
    try:
        with open(CONFIG_FILE, 'r') as f: CONFIG = json.load(f)
        for key, default in [('LANGUAGE', 'en'), ('FRIENDS', {}), ('PLEX_URL', ''), ('OVERSEERR_URL', ''), ('TMDB_API_KEY', ''), ('STREAMING_REGION', 'BR')]:
            if key not in CONFIG: CONFIG[key] = default
        logger.info("Configuração carregada de config.json")
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("config.json não encontrado ou inválido. Use /setup para configurar.")
        CONFIG = {}
        return False

def save_config(new_config=None):
    global CONFIG
    if new_config: CONFIG = new_config
    if 'FRIENDS' not in CONFIG: CONFIG['FRIENDS'] = {}
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
        is_configured = any(CONFIG.get(key) for key in ['RADARR_URL', 'SONARR_URL', 'PLEX_URL', 'OVERSEERR_URL'])
        if not is_configured:
            lang = context.user_data.get('LANGUAGE', 'en')
            if update.callback_query: update.callback_query.answer(get_text('setup_needed', lang), show_alert=True)
            elif update.message: update.message.reply_text(get_text('setup_needed', lang))
            return
        return func(update, context, *args, **kwargs)
    return wrapper

def check_admin(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if context.user_data.get('role') != 'admin':
            (update.callback_query.message if update.callback_query else update.message).reply_text(get_text('admin_only'))
            return
        return func(update, context, *args, **kwargs)
    return wrapper

def api_request(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=15, **kwargs)
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

def check_plex_library(title_to_check):
    if not PLEX_AVAILABLE or not CONFIG.get('PLEX_URL'): return None
    try:
        plex = PlexServer(CONFIG['PLEX_URL'], CONFIG['PLEX_TOKEN'])
        server_name = plex.friendlyName
        logger.info(f"Checando biblioteca do Plex '{server_name}' por título: {title_to_check}")
        results = plex.library.search(title=title_to_check, limit=5)
        for item in results:
            if title_to_check.lower() in item.title.lower():
                item.reload()
                if hasattr(item, 'media') and item.media:
                    logger.info(f"Encontrado '{item.title}' com ficheiros no servidor Plex '{server_name}'.")
                    return {'status': 'available_on_plex', 'message': get_text('plex_found').format(title=item.title, server_name=server_name)}
        raise NotFound
    except NotFound:
        logger.info(f"'{title_to_check}' não encontrado na biblioteca local do Plex server.")
        return None
    except Exception as e:
        logger.error(f"Erro ao checar biblioteca do Plex: {e}"); return None

def check_tmdb_providers(tmdb_id, media_type, title):
    """Verifica provedores de streaming usando a API do TMDB com foco na região do usuário."""
    if not CONFIG.get('TMDB_API_KEY'):
        return {'status': 'error', 'message': get_text('tmdb_not_configured')}
    
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/watch/providers?api_key={CONFIG['TMDB_API_KEY']}"
    data = api_request('get', url)
    if not data or 'results' not in data:
        return None

    results = data['results']
    region = CONFIG.get('STREAMING_REGION', 'BR').upper()
    
    if region in results and 'flatrate' in results[region]:
        provider_names = [p['provider_name'] for p in results[region]['flatrate']]
        logger.info(f"Provedores de streaming encontrados no TMDB para a região {region}: {provider_names}")
        
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
            logger.info(f"Match encontrado no TMDB na região {region}! Mídia disponível em: {unique_services}")
            message = get_text('status_streaming').format(title=title, services=', '.join(unique_services))
            return {'status': 'available_on_streaming', 'message': message}

    logger.info(f"Nenhuma correspondência encontrada na região configurada ({region}) para '{title}'.")
    return None

def get_overseerr_status(tmdb_id, media_type):
    if not CONFIG.get('OVERSEERR_URL'): return None
    url = f"{CONFIG.get('OVERSEERR_URL')}/api/v1/{'tv' if media_type == 'show' else 'movie'}/{tmdb_id}"
    media_data = api_request('get', url, headers={'X-Api-Key': CONFIG.get('OVERSEERR_API_KEY')})
    if not media_data: return None
    title = media_data.get('title', media_data.get('name', ''))
    if (media_info := media_data.get('mediaInfo')) and (status_code := media_info.get('status')) in [1, 2, 3]:
        return {'status': 'pending_on_server', 'message': get_text('status_pending').format(title=title)}
    return None

def add_to_service(service, tmdb_id, title):
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
        
    logger.error(f"Falha ao adicionar '{title}' ao {service.title()}. Resposta: {response}")
    return get_text('add_fail').format(title=title, service=service.title())


def clear_search_data(context: CallbackContext):
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
                 InlineKeyboardButton("🇧🇷 Português", callback_data='lang_pt'),
                 InlineKeyboardButton("🇪🇸 Español", callback_data='lang_es')]]
    update.message.reply_text(get_text('language_prompt'), reply_markup=InlineKeyboardMarkup(keyboard))

def set_language(update: Update, context: CallbackContext):
    query = update.callback_query; query.answer()
    lang_code = query.data.split('_')[1]
    CONFIG['LANGUAGE'] = lang_code
    save_config()
    lang_name = {"en": "English", "pt": "Português", "es": "Español"}.get(lang_code)
    query.edit_message_text(text=get_text('language_set', lang=lang_code).format(lang=lang_name))

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
    update.message.reply_text(get_text('setup_welcome', 'en'))
    return GET_RADARR_URL

def get_text_and_move(update, context, key, prompt_key, next_state):
    context.user_data['setup_data'][key] = update.message.text.strip()
    update.message.reply_text(get_text(prompt_key, 'en'))
    return next_state

def skip_radarr(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_radarr', 'en'))
    for key in ['RADARR_URL', 'RADARR_API_KEY', 'RADARR_QUALITY_PROFILE_ID', 'RADARR_ROOT_FOLDER_PATH']:
        context.user_data['setup_data'][key] = ""
    update.message.reply_text(get_text('setup_sonarr_url', 'en'))
    return GET_SONARR_URL

def skip_sonarr(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_sonarr', 'en'))
    for key in ['SONARR_URL', 'SONARR_API_KEY', 'SONARR_QUALITY_PROFILE_ID', 'SONARR_ROOT_FOLDER_PATH']:
        context.user_data['setup_data'][key] = ""
    update.message.reply_text(get_text('setup_plex_token' if PLEX_AVAILABLE else 'setup_tmdb_api', 'en'))
    return GET_PLEX_TOKEN if PLEX_AVAILABLE else GET_TMDB_API_KEY

def skip_plex(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_plex', 'en'))
    for key in ['PLEX_TOKEN', 'PLEX_URL']:
        context.user_data['setup_data'][key] = ""
    update.message.reply_text(get_text('setup_tmdb_api', 'en'))
    return GET_TMDB_API_KEY

def skip_tmdb(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_tmdb', 'en'))
    for key in ['TMDB_API_KEY', 'STREAMING_REGION']:
        context.user_data['setup_data'][key] = ""
    update.message.reply_text(get_text('setup_ask_overseerr', 'en'))
    return ASK_OVERSEERR

def skip_overseerr(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_overseerr', 'en'))
    context.user_data['setup_data']['OVERSEERR_URL'] = ""
    context.user_data['setup_data']['OVERSEERR_API_KEY'] = ""
    update.message.reply_text(get_text('setup_streaming', 'en'))
    return GET_STREAMING_SERVICES

def skip_streaming(update: Update, context: CallbackContext):
    update.message.reply_text(get_text('setup_skip_streaming', 'en'))
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
    if update.message.text.lower() in ['yes', 'y', 'sim', 's']:
        update.message.reply_text(get_text('setup_overseerr_url', 'en'))
        return GET_OVERSEERR_URL
    else:
        # This handles the 'no' case
        return skip_overseerr(update, context)

def get_streaming_services(update: Update, context: CallbackContext):
    context.user_data['setup_data']['SUBSCRIBED_SERVICES_CODES'] = [c.strip().lower() for c in update.message.text.split(',')]
    return finish_setup(update, context)

def finish_setup(update, context):
    update.message.reply_text(get_text('setup_finished', 'en'))
    context.user_data['setup_data']['LANGUAGE'] = CONFIG.get('LANGUAGE', 'en')
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
    keyboard = [[*nav_row]]
    if context.user_data.get('role') == 'admin':
        keyboard.append([InlineKeyboardButton(add_btn_text, callback_data=f"add_{media_type}_{tmdb_id}")])
    keyboard.append([InlineKeyboardButton(get_text('cancel_btn'), callback_data="nav_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
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
    if action == "lang": return set_language(update, context)
    if action == "nav":
        if payload[0] == "cancel": 
            query.delete_message(); clear_search_data(context); return
        context.user_data['search_index'] += 1 if payload[0] == "next" else -1
        return display_search_result(update, context)
    
    media_type, tmdb_id_str = payload[0], payload[1]
    tmdb_id = int(tmdb_id_str)

    query.delete_message()
    
    results = context.user_data.get('search_results', [])
    search_index = context.user_data.get('search_index', 0)
    current_item = results[search_index] if search_index < len(results) else None
    title_to_check = current_item.get('title') if current_item else 'this media'
    year_to_check = current_item.get('year') if current_item else None
    
    clear_search_data(context)
    
    status_msg = query.message.reply_text(get_text('status_checking'))
    
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
    """Fornece uma depuração passo a passo do processo de verificação de mídia."""
    if not context.args or len(context.args) < 2 or context.args[0] not in ['movie', 'show']:
        update.message.reply_text("Uso: /debug <movie|show> <query>")
        return
    
    media_type = context.args[0]
    query_str = ' '.join(context.args[1:])
    chat = update.effective_chat
    
    def report(message):
        context.bot.send_message(chat.id, f"🐞 {message}")

    report(f"Iniciando depuração para {media_type} '{query_str}'...")

    report(f"Procurando {media_type} no {'Radarr' if media_type == 'movie' else 'Sonarr'}...")
    results = search_radarr(query_str) if media_type == 'movie' else search_sonarr(query_str)
    if not results:
        report("Nenhum resultado encontrado no Radarr/Sonarr. Abortando.")
        return
    
    item = results[0] 
    title_to_check = item.get('title')
    year_to_check = item.get('year')
    tmdb_id = item.get('tmdbId')
    report(f"Encontrado '{title_to_check}' ({year_to_check}) com TMDB ID {tmdb_id}.")

    report("---")
    report("Verificando a biblioteca local do Plex...")
    if (plex_lib_check := check_plex_library(title_to_check)):
        report(f"SUCESSO: Encontrado na biblioteca local do Plex. Mensagem: {plex_lib_check['message']}")
        return report("Depuração finalizada.")
    report("Não encontrado na biblioteca local do Plex.")

    report("---")
    report("Verificando provedores do TMDB...")
    if (tmdb_check := check_tmdb_providers(tmdb_id, media_type, title_to_check)):
         if tmdb_check.get('status') == 'error':
             report(f"ERRO: {tmdb_check['message']}")
         else:
             report(f"SUCESSO: Encontrado via TMDB. Mensagem: {tmdb_check['message']}")
         return report("Depuração finalizada.")
    report("Nenhuma correspondência encontrada via TMDB.")
    
    report("---")
    report("Depuração finalizada.")

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
    # Adicionar handlers de /skip manualmente para cada seção
    radarr_range = range(GET_RADARR_URL, GET_SONARR_URL)
    sonarr_range = range(GET_SONARR_URL, GET_PLEX_TOKEN)
    plex_range = [GET_PLEX_TOKEN, GET_PLEX_URL] if PLEX_AVAILABLE else []
    tmdb_range = [GET_TMDB_API_KEY, GET_STREAMING_REGION]
    overseerr_range = [ASK_OVERSEERR, GET_OVERSEERR_URL, GET_OVERSEERR_API]
    streaming_range = [GET_STREAMING_SERVICES]

    for state in setup_conv.states:
        if state in radarr_range:
            setup_conv.states[state].append(CommandHandler('skip', skip_radarr))
        if state in sonarr_range:
            setup_conv.states[state].append(CommandHandler('skip', skip_sonarr))
        if state in plex_range:
            setup_conv.states[state].append(CommandHandler('skip', skip_plex))
        if state in tmdb_range:
            setup_conv.states[state].append(CommandHandler('skip', skip_tmdb))
        if state in overseerr_range:
            setup_conv.states[state].append(CommandHandler('skip', skip_overseerr))
        if state in streaming_range:
            setup_conv.states[state].append(CommandHandler('skip', skip_streaming))
    
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(login_conv)
    dispatcher.add_handler(CommandHandler("logout", logout))
    dispatcher.add_handler(CommandHandler("auth", auth_command))
    dispatcher.add_handler(CommandHandler("friends", friends_command))
    dispatcher.add_handler(setup_conv)
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("streaming", streaming_command))
    dispatcher.add_handler(CommandHandler("language", language_command))
    dispatcher.add_handler(CommandHandler("movie", lambda u,c: search_media(u,c,'movie')))
    dispatcher.add_handler(CommandHandler("show", lambda u,c: search_media(u,c,'show')))
    dispatcher.add_handler(CommandHandler("debug", debug_media))
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    
    load_config()
    logger.info("Bot iniciado e escutando...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.critical(f"O bot encontrou um erro fatal: {e}", exc_info=True)
        sys.exit(1)
