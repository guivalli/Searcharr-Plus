#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Searchrr Plus - Um bot robusto de gerenciamento de mídia para Telegram.

Este script implementa um bot de Telegram para buscar filmes e séries,
verificar sua disponibilidade no Plex, serviços de streaming e Overseerr,
e adicioná-los ao Radarr ou Sonarr caso não estejam disponíveis.

Versão estável combinando e corrigindo os problemas de versões anteriores.
"""

import logging
import os
import json
import secrets
from functools import wraps
from datetime import datetime, timedelta

# --- Dependências ---
# Certifique-se de instalar com:
# pip install python-telegram-bot==13.15 python-dotenv requests plexapi

from dotenv import load_dotenv
import requests
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound as PlexNotFound

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ParseMode,
    InputMediaPhoto
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
)

# --- Configuração Inicial ---

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Cria as pastas necessárias se não existirem
os.makedirs('logs', exist_ok=True)
os.makedirs('config', exist_ok=True)

# Configuração de logging para um arquivo
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/searchrr_plus.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Constantes ---
CONFIG_FILE = "config/config.json"

# Mapeamento de palavras-chave para códigos de serviços de streaming
KEYWORD_MAP = {
    'nfx': ('netflix',),
    'amp': ('amazon prime video', 'prime video'),
    'max': ('max', 'hbo max'),
    'dnp': ('disney plus', 'disney+'),
    'hlu': ('hulu',),
    'apt': ('apple tv plus', 'apple tv+', 'appletv', 'apple itunes'),
    'pmp': ('paramount plus', 'paramount+'),
    'pck': ('peacock', 'peacock premium'),
    'cru': ('crunchyroll',),
    'sho': ('showtime',),
    'glb': ('globoplay',),
    'sp': ('star+',),
}


# Estados do ConversationHandler para autenticação e configuração
(
    # Auth
    ASK_FRIEND_CODE, ASK_ADMIN_USER, ASK_ADMIN_PASS,
    # Setup
    SETUP_PLEX_URL, SETUP_PLEX_TOKEN,
    SETUP_TMDB_API_KEY, SETUP_TMDB_REGION,
    SETUP_SERVICES_CODES,
    SETUP_RADARR_URL, SETUP_RADARR_API_KEY, SETUP_RADARR_QUALITY_ID, SETUP_RADARR_ROOT_FOLDER,
    SETUP_SONARR_URL, SETUP_SONARR_API_KEY, SETUP_SONARR_QUALITY_ID, SETUP_SONARR_LANG_ID, SETUP_SONARR_ROOT_FOLDER,
    SETUP_OVERSEERR_URL, SETUP_OVERSEERR_API_KEY
) = range(19)


# --- Gerenciamento de Configuração ---

def load_config():
    """Carrega a configuração do config.json, criando-o se não existir."""
    if not os.path.exists(CONFIG_FILE):
        logger.warning(f"Arquivo '{CONFIG_FILE}' não encontrado. Criando um novo com valores padrão.")
        default_config = {
            "admin_user_id": None,
            "friend_user_ids": [],
            "friend_codes": {},
            "plex": {"url": "", "token": ""},
            "tmdb": {"api_key": "", "region": "BR"},
            "radarr": {"url": "", "api_key": "", "quality_profile_id": "1", "root_folder_path": ""},
            "sonarr": {"url": "", "api_key": "", "quality_profile_id": "1", "language_profile_id": "1", "root_folder_path": ""},
            "overseerr": {"url": "", "api_key": ""},
            "subscribed_services": []
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Erro ao carregar o arquivo de configuração: {e}")
        # Retorna um dicionário vazio para evitar que o bot quebre
        return {}

def save_config(config_dict):
    """Salva o dicionário de configuração no arquivo definido pela constante CONFIG_FILE."""
    try:
        # A constante CONFIG_FILE aponta para 'config/config.json'
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=4)
        logger.info(f"Configuração salva com sucesso em '{CONFIG_FILE}'.")
        return True
    except IOError as e:
        logger.error(f"Erro ao salvar o arquivo de configuração '{CONFIG_FILE}': {e}")
        return False

# Carrega a configuração na inicialização do bot
CONFIG = load_config()


# --- Autenticação & Decorators ---

def is_admin(user_id):
    """Verifica se um user_id pertence ao admin."""
    return user_id == CONFIG.get("admin_user_id")

def admin_required(func):
    """Decorator para restringir o acesso a comandos de administrador."""
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        if not is_admin(user_id):
            update.message.reply_text("⛔ Este comando é apenas para o administrador.")
            return
        return func(update, context, *args, **kwargs)
    return wrapped

def auth_required(func):
    """Decorator para garantir que o usuário está autenticado (admin ou amigo)."""
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        if not (is_admin(user_id) or user_id in CONFIG.get("friend_user_ids", [])):
            message = update.message or update.callback_query.message
            message.reply_text("🚫 Você precisa estar autenticado. Por favor, use /start.")
            return
        return func(update, context, *args, **kwargs)
    return wrapped

def config_required(section):
    """Decorator para verificar se uma seção específica da configuração existe."""
    def decorator(func):
        @wraps(func)
        def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
            is_configured = True
            conf_section = CONFIG.get(section.lower(), {})
            if section.lower() == 'radarr' or section.lower() == 'sonarr':
                if not all(conf_section.get(k) for k in ['url', 'api_key', 'root_folder_path']):
                    is_configured = False
            elif not all(conf_section.values()):
                 is_configured = False

            if not is_configured:
                message = update.message or update.callback_query.message
                message.reply_text(f"⚠️ A seção '{section}' não está configurada. O admin deve usar /setup.")
                return
            return func(update, context, *args, **kwargs)
        return wrapped
    return decorator


# --- Funções de API e Lógica de Verificação ---

def _api_get_request(url, params=None, headers=None):
    """Função auxiliar para requisições GET, com logging de erro."""
    try:
        res = requests.get(url, params=params, headers=headers, timeout=20)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Falha na requisição GET para {url}: {e}")
        return None

def _api_post_request(url, json_payload=None, headers=None):
    """Função auxiliar para requisições POST, com logging de erro."""
    try:
        res = requests.post(url, json=json_payload, headers=headers, timeout=20)
        res.raise_for_status()
        # Algumas APIs retornam 201 (Created) sem conteúdo JSON
        if res.status_code in [200, 201] and res.content:
            return res.json()
        return {"status": "success", "code": res.status_code}
    except requests.exceptions.RequestException as e:
        logger.error(f"Falha na requisição POST para {url}: {e}")
        if e.response is not None:
            logger.error(f"Resposta da API: {e.response.text}")
            try:
                return e.response.json() # Tenta retornar o erro da API
            except json.JSONDecodeError:
                return {"error": e.response.text}
        return {"error": str(e)}

# --- Cascata de Verificação de Mídia ---

def check_plex_library(title, year):
    """Verificação 1: Checa se o item já existe na biblioteca do Plex."""
    plex_config = CONFIG.get('plex', {})
    if not all(plex_config.get(k) for k in ['url', 'token']):
        return None
    try:
        plex = PlexServer(plex_config['url'], plex_config['token'])
        # Busca pelo título e filtra pelo ano para maior precisão
        results = plex.search(title)
        for item in results:
            if hasattr(item, 'year') and item.year == year:
                 if hasattr(item, 'media') and item.media:
                    logger.info(f"Mídia '{title}' encontrada no Plex.")
                    return f"✅ '{item.title}' já está disponível no seu Plex: {plex.friendlyName}."
    except PlexNotFound:
        pass # Normal se não encontrar
    except Exception as e:
        logger.error(f"Erro ao verificar a biblioteca do Plex: {e}")
    return None

@config_required('TMDB')
def check_streaming_services(tmdb_id, media_type, title):
    """Verificação 2: Checa provedores de streaming via TMDB."""
    tmdb_config = CONFIG.get('tmdb')
    region = tmdb_config.get('region', 'BR')
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/watch/providers"
    params = {'api_key': tmdb_config['api_key']}
    data = _api_get_request(url, params)

    if not data or region not in data.get('results', {}):
        return None

    region_data = data['results'][region]
    provider_names = []
    # Verifica streaming gratuito, com anúncios e por assinatura
    for provider_type in ['flatrate', 'ads', 'free']:
        if provider_type in region_data:
            provider_names.extend([p['provider_name'] for p in region_data[provider_type]])

    if not provider_names:
        return None

    user_services = CONFIG.get("subscribed_services", [])
    available_on = set()
    for provider in provider_names:
        provider_lower = provider.lower()
        for code in user_services:
            keywords = KEYWORD_MAP.get(code.lower(), ())
            if any(keyword in provider_lower for keyword in keywords):
                available_on.add(provider)
                break # Evita adicionar o mesmo provedor múltiplas vezes

    if available_on:
        services_str = ', '.join(sorted(list(available_on)))
        logger.info(f"Mídia '{title}' encontrada nos serviços de streaming: {services_str}")
        return f"📺 '{title}' está disponível para streaming em: {services_str}."

    return None

def check_overseerr(tmdb_id, media_type):
    """Verificação 3: Checa por pedidos existentes no Overseerr."""
    ov_config = CONFIG.get('overseerr', {})
    if not all(ov_config.get(k) for k in ['url', 'api_key']):
        return None
    
    # A API do Overseerr usa 'tv' ou 'movie'
    internal_media_type = 'tv' if media_type == 'show' else 'movie'
    url = f"{ov_config['url'].rstrip('/')}/api/v1/request"
    headers = {'X-Api-Key': ov_config['api_key']}
    
    # Busca por todos os pedidos e filtra pelo tmdbId
    all_requests = _api_get_request(url, headers=headers)
    if all_requests and 'results' in all_requests:
        for req in all_requests['results']:
            if req['media'].get('tmdbId') == tmdb_id:
                logger.info(f"Mídia com TMDB ID {tmdb_id} já foi pedida no Overseerr.")
                title = req['media'].get('title') or req['media'].get('name')
                return f"⏳ '{title}' já foi pedido no Overseerr e está pendente."
    return None

def add_to_arr_service(media_info, service_name):
    """Verificação 4: Adiciona a mídia ao Radarr ou Sonarr."""
    config = CONFIG.get(service_name.lower())
    if not all(config.get(k) for k in ['url', 'api_key', 'quality_profile_id', 'root_folder_path']):
        return f"⚠️ {service_name.capitalize()} não está totalmente configurado."

    api_path = 'movie' if service_name == 'radarr' else 'series'
    url = f"{config['url'].rstrip('/')}/api/v3/{api_path}"
    headers = {'X-Api-Key': config['api_key']}
    
    payload = {
        "title": media_info['title'],
        "qualityProfileId": int(config['quality_profile_id']),
        "rootFolderPath": config['root_folder_path'],
        "monitored": True,
        "tmdbId": media_info['tmdb_id'] # Comum para ambos agora
    }

    if service_name == 'radarr':
        payload['addOptions'] = {"searchForMovie": True}
    else: # Sonarr
        payload['languageProfileId'] = int(config.get('language_profile_id', 1))
        payload['addOptions'] = {"searchForMissingEpisodes": True}
        # Sonarr precisa do tvdbId, buscamos ele
        tmdb_key = CONFIG.get('tmdb', {}).get('api_key')
        if not tmdb_key: return "⚠️ Chave de API do TMDB não configurada para buscar TVDB ID."
        
        ids_url = f"https://api.themoviedb.org/3/tv/{media_info['tmdb_id']}/external_ids?api_key={tmdb_key}"
        external_ids = _api_get_request(ids_url)
        if not external_ids or not external_ids.get('tvdb_id'):
            return f"❌ Não foi possível encontrar o TVDB ID para '{media_info['title']}'. Não pode ser adicionado ao Sonarr."
        payload['tvdbId'] = external_ids['tvdb_id']

    # Antes de adicionar, verifica se já existe
    all_items = _api_get_request(url, headers=headers)
    if all_items and any(item.get('tmdbId') == media_info['tmdb_id'] for item in all_items):
        return f"ℹ️ '{media_info['title']}' já existe no {service_name.capitalize()}."

    response = _api_post_request(url, json_payload=payload, headers=headers)

    if response and response.get('title') == media_info['title']:
        return f"✅ '{media_info['title']}' foi adicionado ao {service_name.capitalize()} e a busca foi iniciada."
    elif response and any("already been added" in str(msg) for msg in response.get('errorMessage', [])):
        return f"ℹ️ '{media_info['title']}' já existe no {service_name.capitalize()}."
    else:
        logger.error(f"Falha ao adicionar ao {service_name.capitalize()}. Resposta: {response}")
        return f"❌ Falha ao adicionar '{media_info['title']}' ao {service_name.capitalize()}."

# --- Handlers de Comandos ---

def start_cmd(update: Update, context: CallbackContext) -> int:
    """Lida com o comando /start e inicia a autenticação se necessário."""
    global CONFIG
    CONFIG = load_config() # Recarrega a config para pegar novos amigos
    user_id = update.effective_user.id

    if is_admin(user_id):
        update.message.reply_text("✅ Autenticado como Admin. Bem-vindo de volta!")
        return ConversationHandler.END
    if user_id in CONFIG.get("friend_user_ids", []):
        update.message.reply_text("✅ Autenticado como Amigo. Bem-vindo de volta!")
        return ConversationHandler.END

    # Se o admin ainda não foi definido, o primeiro usuário se torna um
    if not CONFIG.get("admin_user_id"):
        # Verifica se as credenciais estão no .env
        if not (os.getenv("BOT_USER") and os.getenv("BOT_PASSWORD")):
            update.message.reply_text("🚨 ERRO CRÍTICO: As variáveis BOT_USER e BOT_PASSWORD não estão definidas no arquivo .env. O bot não pode ser configurado.")
            return ConversationHandler.END
            
        context.user_data['admin_id_to_set'] = user_id
        update.message.reply_text("🔑 Bem-vindo à configuração inicial! Por favor, insira o nome de usuário do admin (definido em .env):")
        return ASK_ADMIN_USER

    update.message.reply_text("👋 Bem-vindo! Se você tem um código de amigo, por favor, insira-o agora. Ou digite /cancelar.")
    return ASK_FRIEND_CODE

def ask_admin_user_handler(update: Update, context: CallbackContext) -> int:
    """Valida o nome de usuário do admin."""
    if update.message.text.strip() == os.getenv("BOT_USER"):
        update.message.reply_text("🔑 Ótimo. Agora, por favor, insira a senha do admin:")
        return ASK_ADMIN_PASS
    else:
        update.message.reply_text("❌ Nome de usuário incorreto. Tente novamente ou peça para o dono do bot verificar o arquivo .env.")
        return ASK_ADMIN_USER

def ask_admin_pass_handler(update: Update, context: CallbackContext) -> int:
    """Valida a senha do admin e finaliza a configuração inicial."""
    if update.message.text.strip() == os.getenv("BOT_PASSWORD"):
        user_id = context.user_data.get('admin_id_to_set')
        CONFIG['admin_user_id'] = user_id
        save_config(CONFIG)
        update.message.reply_text("✅ Administrador definido com sucesso! Bem-vindo.\n\nAgora, vamos configurar os serviços. Use o comando /setup.")
        return ConversationHandler.END
    else:
        update.message.reply_text("❌ Senha incorreta. Tente novamente.")
        return ASK_ADMIN_PASS

def ask_friend_code_handler(update: Update, context: CallbackContext) -> int:
    """Valida um código de amigo."""
    code = update.message.text.strip()
    
    # Limpa códigos expirados
    for c, data in list(CONFIG.get('friend_codes', {}).items()):
        if datetime.fromisoformat(data['expires']) < datetime.now():
            del CONFIG['friend_codes'][c]

    if code in CONFIG.get('friend_codes', {}):
        CONFIG.setdefault('friend_user_ids', []).append(update.effective_user.id)
        del CONFIG['friend_codes'][code] # Código de uso único
        save_config(CONFIG)
        update.message.reply_text("✅ Código de amigo aceito! Bem-vindo(a).")
        help_cmd(update, context)
        return ConversationHandler.END
    else:
        update.message.reply_text("❌ Código de amigo inválido ou expirado. Tente novamente ou digite /cancelar.")
        return ASK_FRIEND_CODE

def cancel_auth(update: Update, context: CallbackContext) -> int:
    """Cancela a conversa de autenticação."""
    update.message.reply_text("Autenticação cancelada.")
    return ConversationHandler.END


@admin_required
def addfriend_cmd(update: Update, context: CallbackContext):
    """Gera um novo código de amigo de uso único."""
    code = secrets.token_hex(8)
    expires = (datetime.now() + timedelta(days=1)).isoformat()
    CONFIG.setdefault('friend_codes', {})[code] = {'expires': expires}
    save_config(CONFIG)
    update.message.reply_text(f"🔑 Novo código de amigo de uso único gerado. É válido por 24 horas:\n\n`{code}`", parse_mode=ParseMode.MARKDOWN)

@auth_required
def help_cmd(update: Update, context: CallbackContext):
    """Mostra a mensagem de ajuda com base na função do usuário."""
    if is_admin(update.effective_user.id):
        update.message.reply_text(
            "👑 *Comandos de Admin*\n\n"
            "/movie <título> - Procurar e adicionar um filme.\n"
            "/show <título> - Procurar e adicionar uma série.\n"
            "/addfriend - Gerar um código de amigo.\n"
            "/setup - (Re)configurar o bot.\n"
            "/debug <movie|show> <título> - Diagnosticar a verificação de uma mídia.\n"
            "/help - Mostrar esta mensagem.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        update.message.reply_text(
            "👥 *Comandos de Amigo*\n\n"
            "/movie <título> - Verificar disponibilidade de um filme.\n"
            "/show <título> - Verificar disponibilidade de uma série.\n"
            "/help - Mostrar esta mensagem.",
            parse_mode=ParseMode.MARKDOWN
        )


def _display_search_results(update: Update, context: CallbackContext, results: list, media_type: str):
    """Mostra os resultados da pesquisa do TMDB com navegação."""
    if not results:
        query = " ".join(context.args)
        update.message.reply_text(f"🤷 Nenhum resultado encontrado para '{query}'. Tente ser mais específico.")
        return

    context.user_data['search_results'] = results
    context.user_data['search_index'] = 0
    context.user_data['search_media_type'] = media_type
    
    _send_media_card(update, context)

def _send_media_card(update: Update, context: CallbackContext, chat_id=None, message_id=None):
    """Envia ou edita a mensagem do cartão de mídia com botões."""
    idx = context.user_data['search_index']
    results = context.user_data['search_results']
    item = results[idx]
    media_type = context.user_data['search_media_type']

    is_movie = media_type == 'movie'
    title = item.get('title') if is_movie else item.get('name')
    release_date = item.get('release_date') if is_movie else item.get('first_air_date', '')
    year = release_date.split('-')[0] if release_date else 'N/A'
    overview = item.get('overview', 'Sem sinopse disponível.')
    tmdb_id = item['id']
    poster_path = item.get('poster_path')
    image_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else f"https://placehold.co/500x750/1c1c1e/ffffff?text={requests.utils.quote(title)}"

    caption = f"*{title} ({year})*\n\n{overview[:700]}"
    
    action_text = "➕ Adicionar"
    callback_data = f"add_{media_type}_{tmdb_id}"
    
    buttons = []
    # Apenas admins podem ver o botão de adicionar
    if is_admin(update.effective_user.id):
         buttons.append([InlineKeyboardButton(action_text, callback_data=callback_data)])
    else: # Amigos veem um botão para checar status
        buttons.append([InlineKeyboardButton("🔎 Verificar Disponibilidade", callback_data=callback_data)])

    nav_buttons = []
    if idx > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Anterior", callback_data="nav_prev"))
    if idx < len(results) - 1:
        nav_buttons.append(InlineKeyboardButton("Próximo ➡️", callback_data="nav_next"))
    if nav_buttons:
        buttons.append(nav_buttons)

    keyboard = InlineKeyboardMarkup(buttons)
    effective_chat_id = chat_id or update.effective_chat.id
    
    media = InputMediaPhoto(media=image_url, caption=caption, parse_mode=ParseMode.MARKDOWN)

    if message_id:
        try:
            context.bot.edit_message_media(chat_id=effective_chat_id, message_id=message_id, media=media, reply_markup=keyboard)
        except Exception as e:
            if 'Message is not modified' not in str(e):
                logger.warning(f"Não foi possível editar a mensagem de mídia (provavelmente idêntica): {e}")
    else:
        sent_message = context.bot.send_photo(effective_chat_id, photo=image_url, caption=caption, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        context.user_data['search_message_id'] = sent_message.message_id


@auth_required
@config_required('TMDB')
def search_cmd(update: Update, context: CallbackContext, media_type: str):
    """Lida com os comandos /movie e /show."""
    if not context.args:
        update.message.reply_text(f"Por favor, forneça um título. Uso: /{media_type} <título>")
        return
    
    query = " ".join(context.args)
    tmdb_key = CONFIG.get('tmdb', {}).get('api_key')
    
    internal_media_type = 'tv' if media_type == 'show' else 'movie'
    url = f"https://api.themoviedb.org/3/search/{internal_media_type}"
    params = {'api_key': tmdb_key, 'query': query, 'language': 'pt-BR', 'include_adult': 'false'}
    data = _api_get_request(url, params)
    
    if data and 'results' in data:
        _display_search_results(update, context, data['results'], media_type)
    else:
        update.message.reply_text(f"🤷 Nenhum resultado encontrado para '{query}'.")

def button_callback_handler(update: Update, context: CallbackContext):
    """Lida com todos os cliques em botões inline."""
    query = update.callback_query
    query.answer()
    data = query.data

    if data.startswith("nav_"):
        direction = 1 if data == 'nav_next' else -1
        context.user_data['search_index'] += direction
        _send_media_card(update, context, chat_id=query.message.chat_id, message_id=query.message.message_id)

    elif data.startswith("add_"):
        # Deleta o cartão de busca para não poluir o chat
        query.message.delete()
        
        _, media_type, tmdb_id_str = data.split('_')
        tmdb_id = int(tmdb_id_str)
        
        # Encontra o item selecionado para pegar os detalhes
        item = next((item for item in context.user_data.get('search_results', []) if item['id'] == tmdb_id), None)
        if not item:
            query.message.reply_text("❌ Erro: Não foi possível encontrar os detalhes da mídia selecionada.")
            return

        is_movie = media_type == 'movie'
        title = item.get('title') if is_movie else item.get('name')
        release_date = item.get('release_date') if is_movie else item.get('first_air_date', '')
        year = int(release_date.split('-')[0]) if release_date else 0
        
        media_info = {'title': title, 'year': year, 'tmdb_id': tmdb_id, 'media_type': media_type}

        perform_full_check_and_act(context, media_info, query.message.chat_id, update.effective_user.id)


def perform_full_check_and_act(context: CallbackContext, media_info: dict, chat_id: int, user_id: int):
    """Executa a cascata de verificação completa e age de acordo."""
    title, year, tmdb_id = media_info['title'], media_info['year'], media_info['tmdb_id']
    media_type = 'show' if media_info['media_type'] == 'tv' else 'movie'
    
    status_msg = context.bot.send_message(chat_id, f"🔎 Verificando '{title}'...")

    # 1. Checar Plex
    status_msg.edit_text(f"Verificando Plex para '{title}'...")
    if (plex_result := check_plex_library(title, year)):
        status_msg.edit_text(plex_result)
        return

    # 2. Checar Streaming
    status_msg.edit_text(f"Verificando serviços de streaming para '{title}'...")
    if (streaming_result := check_streaming_services(tmdb_id, media_type, title)):
        status_msg.edit_text(streaming_result)
        return

    # 3. Checar Overseerr
    status_msg.edit_text(f"Verificando pedidos no Overseerr para '{title}'...")
    if (overseerr_result := check_overseerr(tmdb_id, media_type)):
        status_msg.edit_text(overseerr_result)
        return
        
    # 4. Se nada foi encontrado, agir
    status_msg.edit_text(f"'{title}' não parece estar disponível.")
    
    # Apenas admins podem adicionar
    if is_admin(user_id):
        service_to_add = 'radarr' if media_type == 'movie' else 'sonarr'
        add_result = add_to_arr_service(media_info, service_to_add)
        context.bot.send_message(chat_id, add_result)
    else: # Amigos recebem uma mensagem final
        context.bot.send_message(chat_id, f"ℹ️ '{title}' não está disponível. Peça para um administrador adicioná-lo.")
    
    status_msg.delete() # Limpa a mensagem de "Verificando..."

@admin_required
def debug_cmd(update: Update, context: CallbackContext):
    """Executa um diagnóstico passo a passo da verificação de mídia."""
    if len(context.args) < 2:
        update.message.reply_text("Uso: /debug <movie|show> <título>")
        return

    media_type, query = context.args[0].lower(), " ".join(context.args[1:])

    if media_type not in ['movie', 'show']:
        update.message.reply_text("O primeiro argumento deve ser 'movie' ou 'show'.")
        return

    chat_id = update.effective_chat.id

    def report(message):
        """Função auxiliar para enviar mensagens de debug formatadas."""
        context.bot.send_message(chat_id, f"🐛 {message}")

    report(f"Iniciando debug para '{query}' ({media_type}).")

    # Passo 1: Buscar no TMDB para obter dados consistentes
    report("Buscando no TMDB...")
    tmdb_key = CONFIG.get('tmdb', {}).get('api_key')
    if not tmdb_key:
        report("ERRO: Chave de API do TMDB não configurada. Use /setup.")
        return

    internal_media_type = 'tv' if media_type == 'show' else 'movie'
    url = f"https://api.themoviedb.org/3/search/{internal_media_type}"
    params = {'api_key': tmdb_key, 'query': query, 'language': 'pt-BR', 'include_adult': 'false'}
    data = _api_get_request(url, params)

    if not data or not data.get('results'):
        report(f"Nenhum resultado encontrado no TMDB para '{query}'. Debug encerrado.")
        return

    item = data['results'][0] # Pega o primeiro e mais provável resultado
    is_movie = media_type == 'movie'
    title = item.get('title') if is_movie else item.get('name')
    release_date = item.get('release_date') if is_movie else item.get('first_air_date', '')
    year = int(release_date.split('-')[0]) if release_date else 0
    tmdb_id = item['id']
    report(f"TMDB encontrou: '{title}' ({year}) [ID: {tmdb_id}]")
    report("---")

    # Passo 2: Checar Plex
    report("Verificando biblioteca do Plex...")
    plex_result = check_plex_library(title, year)
    if plex_result:
        report(f"SUCESSO: {plex_result}")
    else:
        report("Não encontrado na biblioteca do Plex.")
    report("---")

    # Passo 3: Checar Serviços de Streaming
    report("Verificando serviços de streaming...")
    streaming_result = check_streaming_services(tmdb_id, internal_media_type, title)
    if streaming_result:
        report(f"SUCESSO: {streaming_result}")
    else:
        report("Não encontrado em nenhum serviço de streaming assinado.")
    report("---")

    # Passo 4: Checar Overseerr
    report("Verificando pedidos no Overseerr...")
    overseerr_result = check_overseerr(tmdb_id, internal_media_type)
    if overseerr_result:
        report(f"SUCESSO: {overseerr_result}")
    else:
        report("Nenhum pedido encontrado no Overseerr.")
    report("---")

    report("Debug finalizado.")


# --- Handlers da Conversa de Configuração ---
@admin_required
def setup_cmd(update: Update, context: CallbackContext) -> int:
    """Inicia a conversa de configuração linear."""
    # Uma cópia da configuração atual é armazenada temporariamente.
    # Ela será modificada durante o setup e salva no final do processo.
    context.user_data['setup_data'] = CONFIG.copy() 
    update.message.reply_text(
        "⚙️ Bem-vindo ao assistente de configuração!\n\n"
        "Vamos configurar passo a passo. Use /cancelar a qualquer momento.\n\n"
        "Primeiro, o Plex. Qual a URL do seu servidor? (ex: http://192.168.1.10:32400)"
    )
    return SETUP_PLEX_URL

def setup_plex_url(update: Update, context: CallbackContext) -> int:
    context.user_data['setup_data'].setdefault('plex', {})['url'] = update.message.text.strip()
    update.message.reply_text("Qual o seu Token do Plex (X-Plex-Token)?")
    return SETUP_PLEX_TOKEN

def setup_plex_token(update: Update, context: CallbackContext) -> int:
    context.user_data['setup_data']['plex']['token'] = update.message.text.strip()
    update.message.reply_text("✅ Plex configurado!\n\nAgora o TMDB. Qual sua chave de API (v3)?")
    return SETUP_TMDB_API_KEY

# ... (outros passos de configuração de forma similar)

def setup_tmdb_api_key(update, context):
    context.user_data['setup_data'].setdefault('tmdb', {})['api_key'] = update.message.text.strip()
    update.message.reply_text("Qual sua região para streaming? (ex: BR, US, PT)")
    return SETUP_TMDB_REGION

def setup_tmdb_region(update, context):
    context.user_data['setup_data']['tmdb']['region'] = update.message.text.strip().upper()
    update.message.reply_text("✅ TMDB configurado!\n\nQuais serviços de streaming você assina? Envie os códigos separados por vírgula (ex: nfx,dnp,max).")
    return SETUP_SERVICES_CODES

def setup_services_codes(update, context):
    codes = [c.strip().lower() for c in update.message.text.split(',')]
    context.user_data['setup_data']['subscribed_services'] = codes
    update.message.reply_text(f"✅ Serviços definidos!\n\nAgora o Radarr (para filmes). Qual a URL?")
    return SETUP_RADARR_URL

def setup_radarr_url(update: Update, context: CallbackContext) -> int:
    context.user_data['setup_data'].setdefault('radarr', {})['url'] = update.message.text.strip()
    update.message.reply_text("Qual a Chave de API (API Key) do Radarr?")
    return SETUP_RADARR_API_KEY
    
# ... continue a cadeia para Radarr, Sonarr, Overseerr ...

def setup_radarr_api_key(update, context):
    context.user_data['setup_data']['radarr']['api_key'] = update.message.text.strip()
    update.message.reply_text("Qual o ID do Perfil de Qualidade do Radarr?")
    return SETUP_RADARR_QUALITY_ID

def setup_radarr_quality_id(update, context):
    context.user_data['setup_data']['radarr']['quality_profile_id'] = update.message.text.strip()
    update.message.reply_text("Qual o Caminho da Pasta Raiz (Root Folder Path) do Radarr?")
    return SETUP_RADARR_ROOT_FOLDER

def setup_radarr_root_folder(update, context):
    context.user_data['setup_data']['radarr']['root_folder_path'] = update.message.text.strip()
    update.message.reply_text("✅ Radarr configurado!\n\nAgora o Sonarr (para séries). Qual a URL?")
    return SETUP_SONARR_URL

def setup_sonarr_url(update, context):
    context.user_data['setup_data'].setdefault('sonarr', {})['url'] = update.message.text.strip()
    update.message.reply_text("Qual a Chave de API (API Key) do Sonarr?")
    return SETUP_SONARR_API_KEY
    
def setup_sonarr_api_key(update, context):
    context.user_data['setup_data']['sonarr']['api_key'] = update.message.text.strip()
    update.message.reply_text("Qual o ID do Perfil de Qualidade do Sonarr?")
    return SETUP_SONARR_QUALITY_ID

def setup_sonarr_quality_id(update, context):
    context.user_data['setup_data']['sonarr']['quality_profile_id'] = update.message.text.strip()
    update.message.reply_text("Qual o ID do Perfil de Linguagem do Sonarr?")
    return SETUP_SONARR_LANG_ID
    
def setup_sonarr_lang_id(update, context):
    context.user_data['setup_data']['sonarr']['language_profile_id'] = update.message.text.strip()
    update.message.reply_text("Qual o Caminho da Pasta Raiz (Root Folder Path) do Sonarr?")
    return SETUP_SONARR_ROOT_FOLDER

def setup_sonarr_root_folder(update, context):
    context.user_data['setup_data']['sonarr']['root_folder_path'] = update.message.text.strip()
    update.message.reply_text("✅ Sonarr configurado!\n\nFinalmente, o Overseerr. Qual a URL?")
    return SETUP_OVERSEERR_URL
    
def setup_overseerr_url(update, context):
    context.user_data['setup_data'].setdefault('overseerr', {})['url'] = update.message.text.strip()
    update.message.reply_text("Qual a Chave de API (API Key) do Overseerr?")
    return SETUP_OVERSEERR_API_KEY
    
def setup_overseerr_api_key(update, context):
    context.user_data['setup_data']['overseerr']['api_key'] = update.message.text.strip()
    update.message.reply_text("✅ Overseerr configurado!")
    
    # Este é o passo final da configuração.
    # Os dados temporários são agora salvos no arquivo config.json.
    global CONFIG
    CONFIG = context.user_data['setup_data']
    if save_config(CONFIG):
        update.message.reply_text("💾 Todas as configurações foram salvas com sucesso! O bot está pronto.")
    else:
        update.message.reply_text("❌ Erro ao salvar o arquivo de configuração. Verifique os logs.")
        
    context.user_data.clear()
    return ConversationHandler.END


def cancel_setup(update: Update, context: CallbackContext) -> int:
    """Cancela a conversa de configuração."""
    update.message.reply_text("⚙️ Configuração cancelada.")
    context.user_data.clear()
    return ConversationHandler.END

# --- Função Principal ---
def main() -> None:
    """Inicia o bot e configura os handlers."""
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.critical("Variável de ambiente BOT_TOKEN não definida. O bot não pode iniciar.")
        return

    updater = Updater(bot_token)
    dispatcher = updater.dispatcher

    # Handler para autenticação de admin e amigos
    auth_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_cmd)],
        states={
            ASK_FRIEND_CODE: [MessageHandler(Filters.text & ~Filters.command, ask_friend_code_handler)],
            ASK_ADMIN_USER: [MessageHandler(Filters.text & ~Filters.command, ask_admin_user_handler)],
            ASK_ADMIN_PASS: [MessageHandler(Filters.text & ~Filters.command, ask_admin_pass_handler)],
        },
        fallbacks=[CommandHandler('cancelar', cancel_auth)],
        conversation_timeout=300
    )
    
    # Handler para a configuração passo a passo
    setup_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setup', setup_cmd)],
        states={
            SETUP_PLEX_URL: [MessageHandler(Filters.text & ~Filters.command, setup_plex_url)],
            SETUP_PLEX_TOKEN: [MessageHandler(Filters.text & ~Filters.command, setup_plex_token)],
            SETUP_TMDB_API_KEY: [MessageHandler(Filters.text & ~Filters.command, setup_tmdb_api_key)],
            SETUP_TMDB_REGION: [MessageHandler(Filters.text & ~Filters.command, setup_tmdb_region)],
            SETUP_SERVICES_CODES: [MessageHandler(Filters.text & ~Filters.command, setup_services_codes)],
            SETUP_RADARR_URL: [MessageHandler(Filters.text & ~Filters.command, setup_radarr_url)],
            SETUP_RADARR_API_KEY: [MessageHandler(Filters.text & ~Filters.command, setup_radarr_api_key)],
            SETUP_RADARR_QUALITY_ID: [MessageHandler(Filters.text & ~Filters.command, setup_radarr_quality_id)],
            SETUP_RADARR_ROOT_FOLDER: [MessageHandler(Filters.text & ~Filters.command, setup_radarr_root_folder)],
            SETUP_SONARR_URL: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_url)],
            SETUP_SONARR_API_KEY: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_api_key)],
            SETUP_SONARR_QUALITY_ID: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_quality_id)],
            SETUP_SONARR_LANG_ID: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_lang_id)],
            SETUP_SONARR_ROOT_FOLDER: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_root_folder)],
            SETUP_OVERSEERR_URL: [MessageHandler(Filters.text & ~Filters.command, setup_overseerr_url)],
            SETUP_OVERSEERR_API_KEY: [MessageHandler(Filters.text & ~Filters.command, setup_overseerr_api_key)],
        },
        fallbacks=[CommandHandler('cancelar', cancel_setup)],
        conversation_timeout=600
    )

    dispatcher.add_handler(auth_conv_handler)
    dispatcher.add_handler(setup_conv_handler)
    dispatcher.add_handler(CommandHandler("help", help_cmd))
    dispatcher.add_handler(CommandHandler("addfriend", addfriend_cmd))
    dispatcher.add_handler(CommandHandler("debug", debug_cmd))
    dispatcher.add_handler(CommandHandler("movie", lambda u, c: search_cmd(u, c, 'movie')))
    dispatcher.add_handler(CommandHandler("show", lambda u, c: search_cmd(u, c, 'show')))
    dispatcher.add_handler(CallbackQueryHandler(button_callback_handler))

    updater.start_polling()
    logger.info("Bot iniciado e escutando por comandos...")
    updater.idle()

if __name__ == '__main__':
    main()
