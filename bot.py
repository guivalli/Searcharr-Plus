#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import json
import secrets
from functools import wraps
from datetime import datetime, timedelta

# --- Dependencies ---
# Make sure to install with:
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

# Import the new friend request module
import friend_requests

# --- Initial Setup ---

load_dotenv()
os.makedirs('logs', exist_ok=True)
os.makedirs('config', exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/searchrr_plus.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Constants ---
CONFIG_FILE = "config/config.json"
KEYWORD_MAP = {
    'nfx': ('netflix',), 'amp': ('amazon prime video', 'prime video'), 'max': ('max', 'hbo max'),
    'dnp': ('disney plus', 'disney+'), 'hlu': ('hulu',), 'apt': ('apple tv plus', 'apple tv+', 'appletv'),
    'pmp': ('paramount plus', 'paramount+'), 'pck': ('peacock',), 'cru': ('crunchyroll',),
    'sho': ('showtime',), 'glb': ('globoplay',), 'sp': ('star+',)
}

# ConversationHandler states
(
    # Auth
    AWAIT_LOGIN_USER, AWAIT_LOGIN_PASSWORD, AWAIT_FRIEND_CODE,
    # Setup
    SETUP_MENU,
    SETUP_PLEX_URL, SETUP_PLEX_TOKEN,
    SETUP_TMDB_API_KEY, SETUP_TMDB_REGION,
    SETUP_SERVICES_CODES,
    SETUP_RADARR_URL, SETUP_RADARR_API_KEY, SETUP_RADARR_QUALITY_ID, SETUP_RADARR_ROOT_FOLDER,
    AWAIT_RADARR_4K_CHOICE, SETUP_RADARR_QUALITY_ID_4K, SETUP_RADARR_ROOT_FOLDER_4K,
    SETUP_SONARR_URL, SETUP_SONARR_API_KEY, SETUP_SONARR_QUALITY_ID, SETUP_SONARR_LANG_ID, SETUP_SONARR_ROOT_FOLDER,
    AWAIT_SONARR_4K_CHOICE, SETUP_SONARR_QUALITY_ID_4K, SETUP_SONARR_ROOT_FOLDER_4K,
    SETUP_OVERSEERR_URL, SETUP_OVERSEERR_API_KEY,
    # Friends
    FRIENDS_MENU, AWAIT_FRIEND_NAME_TO_ADD, AWAIT_FRIEND_TO_REMOVE
) = range(29)


# --- Translations ---
translations = {
    'en': {
        "start_message": "👋 Welcome! Please use /login (admin) or /auth (friend) to get started.",
        "login_prompt_user": "🔑 Please enter the admin username:",
        "login_prompt_pass": "🔑 Please enter the password:",
        "login_success": "✅ Login successful! Welcome back.",
        "login_fail": "❌ Incorrect credentials or you are not the designated admin.",
        "login_already_done": "✅ You are already logged in.",
        "logout_success": "✅ You have been successfully logged out.",
        "auth_required": "🚫 You need to be authenticated. Please use /login or /auth.",
        "unauthenticated_message": "You are not logged in. Please use /login or /auth.",
        "admin_required": "⛔ This command is for administrators only.",
        "auth_prompt": "👋 Welcome! Please enter your friend code:",
        "auth_friend_code_invalid": "❌ Invalid or expired friend code. Try again or type /cancel.",
        "auth_friend_code_accepted": "✅ Friend code accepted! Welcome.",
        "auth_cancelled": "Authentication canceled.",
        "search_cancelled": "Ok, search cancelled.",
        "cancel_button": "❌ Cancel",
        "new_friend_code": "🔑 New single-use friend code for '{name}' generated. It is valid for 24 hours:\n\n`{code}`",
        "help_admin": "👑 *Admin Commands*\n\n/movie <title> - Search and add a movie.\n/movie4k <title> - Add a movie in 4K.\n/show <title> - Search and add a series.\n/show4k <title> - Add a series in 4K.\n/check <movie|show> <title> - Check if media is on Plex/Radarr/Sonarr.\n/friends - Manage friend access.\n/setup - (Re)configure the bot.\n/language - Change the bot's language.\n/streaming - List available streaming codes.\n/debug <movie|show> <title> - Diagnose the check for a media.\n/logout - End your session.\n/help - Show this message.",
        "help_friend": "👥 *Friend Commands*\n\n/movie <title> - Check availability of a movie.\n/show <title> - Check availability of a series.\n/friendrequest <movie|show> <title> - Request new media.\n/check <movie|show> <title> - Check if media is on Plex/Radarr/Sonarr.\n/language - Change the bot's language.\n/help - Show this message.",
        "no_results": "🤷 No results found for '{query}'. Try being more specific.",
        "provide_title": "Please provide a title. Usage: /{command} <title>",
        "check_usage": "Usage: /check <movie|show> <title>",
        "friendrequest_usage": "Usage: /friendrequest <movie|show> <title>",
        "add_button": "➕ Add",
        "add_button_4k": "➕ Add 4K",
        "check_button": "🔎 Check Status",
        "nav_prev": "⬅️ Previous",
        "nav_next": "Next ➡️",
        "error_media_details": "❌ Error: Could not find the details of the selected media.",
        "checking_status": "🔎 Checking '{title}'...",
        "media_unavailable": "'{title}' does not seem to be available.",
        "media_unavailable_friend": "ℹ️ '{title}' is not available. Ask an administrator to add it.",
        "request_sent": "✅ Your request for '{title}' has been sent to the admin for approval.",
        "request_limit_reached": "🚫 You have reached your daily request limit of 3 requests.",
        "request_already_in_library": "✅ Great news! '{title}' is already in the library.",
        "request_approved_notification": "🎉 Good news! Your request for '{title}' has been approved and is being added.",
        "request_declined_notification": "😞 Sorry, your request for '{title}' was declined by the admin.",
        "setup_menu_prompt": "⚙️ *Setup Menu*\n\nChoose a section to configure, or reconfigure everything.",
        "setup_section_plex": "Plex",
        "setup_section_tmdb": "TMDB",
        "setup_section_radarr": "Radarr",
        "setup_section_sonarr": "Sonarr",
        "setup_section_overseerr": "Overseerr",
        "setup_section_streaming": "Streaming Services",
        "setup_all_button": "(Re)configure everything",
        "setup_save_exit_button": "💾 Save & Exit",
        "setup_cancelled": "⚙️ Setup canceled.",
        "setup_saved": "💾 All settings have been successfully saved! The bot is ready.",
        "setup_error_saving": "❌ Error saving the configuration file. Check the logs.",
        "setup_ask_4k": "Do you want to configure a separate 4K profile for {service}? (yes/no)",
        "setup_4k_quality_prompt": "What is the 4K Quality Profile ID for {service}?",
        "setup_4k_folder_prompt": "What is the 4K Root Folder Path for {service}?",
        "setup_4k_profile_not_configured": "⚠️ {service} 4K profile is not configured. Please use /setup.",
        "language_prompt": "Please choose your language:",
        "language_set": "✅ Language set to {lang_name}.",
        "plex_found": "✅ '{title}' is already available on your Plex: {server_name}.",
        "streaming_found": "📺 '{title}' is available for streaming on: {services_str}.",
        "streaming_list_header": "📜 *Available Streaming Service Codes*\n\n",
        "overseerr_found": "⏳ '{title}' has already been requested on Overseerr and is pending.",
        "service_add_success": "✅ '{title}' has been added to {service_name} and the search has started.",
        "service_add_exists": "ℹ️ '{title}' already exists in {service_name}.",
        "service_add_fail": "❌ Failed to add '{title}' to {service_name}.",
        "check_sonarr_radarr_found": "✅ '{title}' is already in {service_name}.",
        "check_not_found": "❌ '{title}' was not found in your Plex, Radarr, or Sonarr.",
        "friends_menu_prompt": "👥 *Friends Management*\n\nWhat would you like to do?",
        "friends_button_add": "➕ Add Friend",
        "friends_button_remove": "➖ Remove Friend",
        "friends_button_list": "📋 List Friends",
        "friends_button_back": "⬅️ Back",
        "friends_add_prompt": "Please send the name for the new friend.",
        "friends_remove_prompt": "Select a friend to remove:",
        "friends_no_friends_to_remove": "There are no friends to remove.",
        "friends_list_title": "📋 Friend List",
        "friends_friend_removed": "✅ Friend '{name}' has been successfully removed.",
        "friends_no_friends": "You haven't added any friends yet.",
        "friends_list_format": "- {name}",
        "debug_start": "🐛 Starting debug for '{query}' ({media_type}).",
        "debug_tmdb_search": "Searching on TMDB...",
        "debug_tmdb_found": "TMDB found: '{title}' ({year}) [ID: {tmdb_id}]",
        "debug_tmdb_not_found": "No results found on TMDB for '{query}'. Debug finished.",
        "debug_plex_check": "Verifying Plex library...",
        "debug_plex_success": "SUCCESS: {plex_result}",
        "debug_plex_fail": "Not found in Plex library.",
        "debug_streaming_check": "Verifying streaming services...",
        "debug_streaming_success": "SUCCESS: {streaming_result}",
        "debug_streaming_fail": "Not found on any subscribed streaming service.",
        "debug_overseerr_check": "Verifying requests on Overseerr...",
        "debug_overseerr_success": "SUCCESS: {overseerr_result}",
        "debug_overseerr_fail": "No request found on Overseerr.",
        "debug_end": "Debug finished.",
    },
    'pt': {
        "start_message": "👋 Bem-vindo! Por favor, use /login (admin) ou /auth (amigo) para começar.",
        "login_prompt_user": "🔑 Por favor, digite o nome de usuário do admin:",
        "login_prompt_pass": "🔑 Por favor, digite a senha:",
        "login_success": "✅ Login realizado com sucesso! Bem-vindo(a) de volta.",
        "login_fail": "❌ Credenciais incorretas ou você não é o admin designado.",
        "login_already_done": "✅ Você já está logado.",
        "logout_success": "✅ Você foi desconectado com sucesso.",
        "auth_required": "🚫 Você precisa estar autenticado. Por favor, use /login ou /auth.",
        "unauthenticated_message": "Você não está logado. Por favor, use /login ou envie seu código de amigo com /auth.",
        "admin_required": "⛔ Este comando é apenas para administradores.",
        "auth_prompt": "👋 Bem-vindo! Por favor, insira o seu código de amigo:",
        "auth_friend_code_invalid": "❌ Código de amigo inválido ou expirado. Tente novamente ou digite /cancelar.",
        "auth_friend_code_accepted": "✅ Código de amigo aceito! Bem-vindo(a).",
        "auth_cancelled": "Autenticação cancelada.",
        "search_cancelled": "Ok, busca cancelada.",
        "cancel_button": "❌ Cancelar",
        "new_friend_code": "🔑 Novo código de amigo de uso único para '{name}' gerado. É válido por 24 horas:\n\n`{code}`",
        "help_admin": "👑 *Comandos de Admin*\n\n/movie <título> - Procurar e adicionar um filme.\n/movie4k <título> - Adicionar um filme em 4K.\n/show <título> - Procurar e adicionar uma série.\n/show4k <título> - Adicionar uma série em 4K.\n/check <movie|show> <título> - Checar se a mídia está no Plex/Radarr/Sonarr.\n/friends - Gerenciar amigos.\n/setup - (Re)configurar o bot.\n/language - Alterar o idioma do bot.\n/streaming - Listar códigos de streaming disponíveis.\n/debug <movie|show> <título> - Diagnosticar a verificação de uma mídia.\n/logout - Encerrar sua sessão.\n/help - Mostrar esta mensagem.",
        "help_friend": "👥 *Comandos de Amigo*\n\n/movie <título> - Verificar disponibilidade de um filme.\n/show <título> - Verificar disponibilidade de uma série.\n/friendrequest <movie|show> <título> - Pedir nova mídia.\n/check <movie|show> <título> - Checar se a mídia está no Plex/Radarr/Sonarr.\n/language - Alterar o idioma do bot.\n/help - Mostrar esta mensagem.",
        "no_results": "🤷 Nenhum resultado encontrado para '{query}'. Tente ser mais específico.",
        "provide_title": "Por favor, forneça um título. Uso: /{command} <título>",
        "check_usage": "Uso: /check <movie|show> <título>",
        "friendrequest_usage": "Uso: /friendrequest <movie|show> <título>",
        "add_button": "➕ Adicionar",
        "add_button_4k": "➕ Adicionar 4K",
        "check_button": "🔎 Checar Status",
        "nav_prev": "⬅️ Anterior",
        "nav_next": "Próximo ➡️",
        "error_media_details": "❌ Erro: Não foi possível encontrar os detalhes da mídia selecionada.",
        "checking_status": "🔎 Verificando '{title}'...",
        "media_unavailable": "'{title}' não parece estar disponível.",
        "media_unavailable_friend": "ℹ️ '{title}' não está disponível. Peça para um administrador adicioná-lo.",
        "request_sent": "✅ Seu pedido para '{title}' foi enviado para aprovação do admin.",
        "request_limit_reached": "🚫 Você atingiu seu limite diário de 3 pedidos.",
        "request_already_in_library": "✅ Ótima notícia! '{title}' já está na biblioteca.",
        "request_approved_notification": "🎉 Boas notícias! Seu pedido para '{title}' foi aprovado e está sendo adicionado.",
        "request_declined_notification": "😞 Desculpe, seu pedido para '{title}' foi recusado pelo admin.",
        "setup_menu_prompt": "⚙️ *Menu de Configuração*\n\nEscolha uma seção para configurar, ou reconfigure tudo.",
        "setup_section_plex": "Plex",
        "setup_section_tmdb": "TMDB",
        "setup_section_radarr": "Radarr",
        "setup_section_sonarr": "Sonarr",
        "setup_section_overseerr": "Overseerr",
        "setup_section_streaming": "Serviços de Streaming",
        "setup_all_button": "(Re)configurar tudo",
        "setup_save_exit_button": "💾 Salvar e Sair",
        "setup_cancelled": "⚙️ Configuração cancelada.",
        "setup_saved": "💾 Todas as configurações foram salvas com sucesso! O bot está pronto.",
        "setup_error_saving": "❌ Erro ao salvar o arquivo de configuração. Verifique os logs.",
        "setup_ask_4k": "Você deseja configurar um perfil 4K separado para o {service}? (sim/não)",
        "setup_4k_quality_prompt": "Qual o ID do Perfil de Qualidade 4K do {service}?",
        "setup_4k_folder_prompt": "Qual o Caminho da Pasta Raiz 4K do {service}?",
        "setup_4k_profile_not_configured": "⚠️ O perfil 4K do {service} não está configurado. Por favor, use o /setup.",
        "language_prompt": "Por favor, escolha o seu idioma:",
        "language_set": "✅ Idioma alterado para {lang_name}.",
        "plex_found": "✅ '{title}' já está disponível no seu Plex: {server_name}.",
        "streaming_found": "📺 '{title}' está disponível para streaming em: {services_str}.",
        "streaming_list_header": "📜 *Códigos de Serviços de Streaming Disponíveis*\n\n",
        "overseerr_found": "⏳ '{title}' já foi pedido no Overseerr e está pendente.",
        "service_add_success": "✅ '{title}' foi adicionado ao {service_name} e a busca foi iniciada.",
        "service_add_exists": "ℹ️ '{title}' já existe no {service_name}.",
        "service_add_fail": "❌ Falha ao adicionar '{title}' ao {service_name}.",
        "check_sonarr_radarr_found": "✅ '{title}' já está no {service_name}.",
        "check_not_found": "❌ '{title}' não foi encontrado no seu Plex, Radarr ou Sonarr.",
        "friends_menu_prompt": "👥 *Gerenciamento de Amigos*\n\nO que você gostaria de fazer?",
        "friends_button_add": "➕ Adicionar Amigo",
        "friends_button_remove": "➖ Remover Amigo",
        "friends_button_list": "📋 Listar Amigos",
        "friends_button_back": "⬅️ Voltar",
        "friends_add_prompt": "Por favor, envie o nome para o novo amigo.",
        "friends_remove_prompt": "Selecione um amigo para remover:",
        "friends_no_friends_to_remove": "Não há amigos para remover.",
        "friends_list_title": "📋 Lista de Amigos",
        "friends_friend_removed": "✅ Amigo '{name}' foi removido com sucesso.",
        "friends_no_friends": "Você ainda não adicionou nenhum amigo.",
        "friends_list_format": "- {name}",
        "debug_start": "🐛 Iniciando debug para '{query}' ({media_type}).",
        "debug_tmdb_search": "Buscando no TMDB...",
        "debug_tmdb_found": "TMDB encontrou: '{title}' ({year}) [ID: {tmdb_id}]",
        "debug_tmdb_not_found": "Nenhum resultado encontrado no TMDB para '{query}'. Debug encerrado.",
        "debug_plex_check": "Verificando biblioteca do Plex...",
        "debug_plex_success": "SUCESSO: {plex_result}",
        "debug_plex_fail": "Não encontrado na biblioteca do Plex.",
        "debug_streaming_check": "Verificando serviços de streaming...",
        "debug_streaming_success": "SUCESSO: {streaming_result}",
        "debug_streaming_fail": "Não encontrado em nenhum serviço de streaming assinado.",
        "debug_overseerr_check": "Verificando pedidos no Overseerr...",
        "debug_overseerr_success": "SUCESSO: {overseerr_result}",
        "debug_overseerr_fail": "Nenhum pedido encontrado no Overseerr.",
        "debug_end": "Debug finalizado.",
    },
    'es': {
        "start_message": "👋 ¡Bienvenido! Por favor, usa /login (admin) o /auth (amigo) para empezar.",
        "login_prompt_user": "🔑 Por favor, introduce el nombre de usuario del admin:",
        "login_prompt_pass": "🔑 Por favor, introduce la contraseña:",
        "login_success": "✅ ¡Inicio de sesión exitoso! Bienvenido de nuevo.",
        "login_fail": "❌ Credenciales incorrectas o no eres el admin designado.",
        "login_already_done": "✅ Ya has iniciado sesión.",
        "logout_success": "✅ Has cerrado la sesión correctamente.",
        "auth_required": "🚫 Necesitas estar autenticado. Por favor, usa /login o /auth.",
        "unauthenticated_message": "No estás conectado. Por favor, usa /login o envía tu código de amigo con /auth.",
        "admin_required": "⛔ Este comando es solo para administradores.",
        "auth_prompt": "👋 ¡Bienvenido! Por favor, introduce tu código de amigo:",
        "auth_friend_code_invalid": "❌ Código de amigo inválido o caducado. Inténtalo de nuevo o escribe /cancelar.",
        "auth_friend_code_accepted": "✅ ¡Código de amigo aceptado! Bienvenido.",
        "auth_cancelled": "Autenticación cancelada.",
        "search_cancelled": "Ok, búsqueda cancelada.",
        "cancel_button": "❌ Cancelar",
        "new_friend_code": "🔑 Nuevo código de amigo de un solo uso para '{name}' generado. Es válido por 24 horas:\n\n`{code}`",
        "help_admin": "👑 *Comandos de Admin*\n\n/movie <título> - Buscar y añadir una película.\n/movie4k <título> - Añadir una película en 4K.\n/show <título> - Buscar y añadir una serie.\n/show4k <título> - Añadir una serie en 4K.\n/check <movie|show> <título> - Comprobar si el medio está en Plex/Radarr/Sonarr.\n/friends - Gestionar amigos.\n/setup - (Re)configurar el bot.\n/language - Cambiar el idioma del bot.\n/streaming - Listar códigos de streaming disponibles.\n/debug <movie|show> <título> - Diagnosticar la verificación de un medio.\n/logout - Cerrar tu sesión.\n/help - Mostrar este mensaje.",
        "help_friend": "👥 *Comandos de Amigo*\n\n/movie <título> - Comprobar la disponibilidad de una película.\n/show <título> - Comprobar la disponibilidad de una serie.\n/friendrequest <movie|show> <título> - Solicitar nuevo medio.\n/check <movie|show> <título> - Comprobar si el medio está en Plex/Radarr/Sonarr.\n/language - Cambiar el idioma del bot.\n/help - Mostrar este mensaje.",
        "no_results": "🤷 No se encontraron resultados para '{query}'. Intenta ser más específico.",
        "provide_title": "Por favor, proporciona un título. Uso: /{command} <título>",
        "check_usage": "Uso: /check <movie|show> <título>",
        "friendrequest_usage": "Uso: /friendrequest <movie|show> <título>",
        "add_button": "➕ Añadir",
        "add_button_4k": "➕ Añadir 4K",
        "check_button": "🔎 Comprobar Estado",
        "nav_prev": "⬅️ Anterior",
        "nav_next": "Siguiente ➡️",
        "error_media_details": "❌ Error: No se pudieron encontrar los detalles del medio seleccionado.",
        "checking_status": "🔎 Comprobando '{title}'...",
        "media_unavailable": "'{title}' no parece estar disponible.",
        "media_unavailable_friend": "ℹ️ '{title}' no está disponible. Pide a un administrador que lo añada.",
        "request_sent": "✅ Tu solicitud para '{title}' ha sido enviada al admin para su aprobación.",
        "request_limit_reached": "🚫 Has alcanzado tu límite diario de 3 solicitudes.",
        "request_already_in_library": "✅ ¡Buenas noticias! '{title}' ya está en la biblioteca.",
        "request_approved_notification": "🎉 ¡Buenas noticias! Tu solicitud para '{title}' ha sido aprobada y se está añadiendo.",
        "request_declined_notification": "😞 Lo siento, tu solicitud para '{title}' fue rechazada por el admin.",
        "setup_menu_prompt": "⚙️ *Menú de Configuración*\n\nElige una sección para configurar, o reconfigura todo.",
        "setup_section_plex": "Plex",
        "setup_section_tmdb": "TMDB",
        "setup_section_radarr": "Radarr",
        "setup_section_sonarr": "Sonarr",
        "setup_section_overseerr": "Overseerr",
        "setup_section_streaming": "Servicios de Streaming",
        "setup_all_button": "(Re)configurar todo",
        "setup_save_exit_button": "💾 Guardar y Salir",
        "setup_cancelled": "⚙️ Configuración cancelada.",
        "setup_saved": "💾 ¡Todos los ajustes se han guardado con éxito! El bot está listo.",
        "setup_error_saving": "❌ Error al guardar el archivo de configuración. Comprueba los logs.",
        "setup_ask_4k": "¿Deseas configurar un perfil 4K separado para {service}? (si/no)",
        "setup_4k_quality_prompt": "¿Cuál es el ID del Perfil de Calidad 4K de {service}?",
        "setup_4k_folder_prompt": "¿Cuál es la Ruta de la Carpeta Raíz 4K de {service}?",
        "setup_4k_profile_not_configured": "⚠️ El perfil 4K de {service} no está configurado. Por favor, usa /setup.",
        "language_prompt": "Por favor, elige tu idioma:",
        "language_set": "✅ Idioma cambiado a {lang_name}.",
        "plex_found": "✅ '{title}' ya está disponible en tu Plex: {server_name}.",
        "streaming_found": "📺 '{title}' está disponible para streaming en: {services_str}.",
        "streaming_list_header": "📜 *Códigos de Servicios de Streaming Disponibles*\n\n",
        "overseerr_found": "⏳ '{title}' ya ha sido solicitado en Overseerr y está pendiente.",
        "service_add_success": "✅ '{title}' ha sido añadido a {service_name} y la búsqueda ha comenzado.",
        "service_add_exists": "ℹ️ '{title}' ya existe en {service_name}.",
        "service_add_fail": "❌ Fallo al añadir '{title}' a {service_name}.",
        "check_sonarr_radarr_found": "✅ '{title}' ya está en {service_name}.",
        "check_not_found": "❌ '{title}' no se encontró en tu Plex, Radarr, o Sonarr.",
        "friends_menu_prompt": "👥 *Gestión de Amigos*\n\n¿Qué te gustaría hacer?",
        "friends_button_add": "➕ Añadir Amigo",
        "friends_button_remove": "➖ Eliminar Amigo",
        "friends_button_list": "📋 Listar Amigos",
        "friends_button_back": "⬅️ Volver",
        "friends_add_prompt": "Por favor, envía el nombre para el nuevo amigo.",
        "friends_remove_prompt": "Selecciona un amigo para eliminar:",
        "friends_no_friends_to_remove": "No hay amigos para eliminar.",
        "friends_list_title": "📋 Lista de Amigos",
        "friends_friend_removed": "✅ Amigo '{name}' ha sido eliminado con éxito.",
        "friends_no_friends": "Aún no has añadido ningún amigo.",
        "friends_list_format": "- {name}",
        "debug_start": "🐛 Iniciando debug para '{query}' ({media_type}).",
        "debug_tmdb_search": "Buscando en TMDB...",
        "debug_tmdb_found": "TMDB encontró: '{title}' ({year}) [ID: {tmdb_id}]",
        "debug_tmdb_not_found": "No se encontraron resultados en TMDB para '{query}'. Debug finalizado.",
        "debug_plex_check": "Verificando la biblioteca de Plex...",
        "debug_plex_success": "ÉXITO: {plex_result}",
        "debug_plex_fail": "No encontrado en la biblioteca de Plex.",
        "debug_streaming_check": "Verificando servicios de streaming...",
        "debug_streaming_success": "ÉXITO: {streaming_result}",
        "debug_streaming_fail": "No encontrado en ningún servicio de streaming suscrito.",
        "debug_overseerr_check": "Verificando solicitudes en Overseerr...",
        "debug_overseerr_success": "ÉXITO: {overseerr_result}",
        "debug_overseerr_fail": "No se encontró ninguna solicitud en Overseerr.",
        "debug_end": "Debug finalizado.",
    }
}

def get_text(key, lang='en'):
    """Fetches a translation string, falling back to English."""
    return translations.get(lang, translations.get('en', {})).get(key, f"_{key.upper()}_")


# --- Configuration Management ---

def load_config():
    """Loads the configuration from config.json, creating it if it doesn't exist."""
    if not os.path.exists(CONFIG_FILE):
        logger.warning(f"File '{CONFIG_FILE}' not found. Creating a new one with default values.")
        default_config = {
            "admin_user_id": None,
            "friend_user_ids": {}, # Use dict for {user_id: name}
            "friend_codes": {},
            "language": "en", # Default to English
            "plex": {"url": "", "token": ""},
            "tmdb": {"api_key": "", "region": "BR"},
            "radarr": {
                "url": "", "api_key": "", "quality_profile_id": "1", "root_folder_path": "",
                "quality_profile_id_4k": "", "root_folder_path_4k": ""
            },
            "sonarr": {
                "url": "", "api_key": "", "quality_profile_id": "1", "language_profile_id": "1", "root_folder_path": "",
                "quality_profile_id_4k": "", "root_folder_path_4k": ""
            },
            "overseerr": {"url": "", "api_key": ""},
            "subscribed_services": []
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Ensure new keys exist for backward compatibility
            if 'language' not in config: config['language'] = 'en'
            if 'quality_profile_id_4k' not in config.get('radarr', {}):
                config.setdefault('radarr', {})['quality_profile_id_4k'] = ""
                config.setdefault('radarr', {})['root_folder_path_4k'] = ""
            if 'quality_profile_id_4k' not in config.get('sonarr', {}):
                config.setdefault('sonarr', {})['quality_profile_id_4k'] = ""
                config.setdefault('sonarr', {})['root_folder_path_4k'] = ""
            return config
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading configuration file: {e}")
        return {}

def save_config(config_dict):
    """Saves the configuration dictionary to the file defined by CONFIG_FILE constant."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=4)
        logger.info(f"Configuration successfully saved to '{CONFIG_FILE}'.")
        return True
    except IOError as e:
        logger.error(f"Error saving configuration file '{CONFIG_FILE}': {e}")
        return False

CONFIG = load_config()


# --- Authentication & Decorators ---

def is_admin(user_id):
    return user_id == CONFIG.get("admin_user_id")

def admin_required(func):
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        if context.user_data.get('role') != 'admin':
            update.message.reply_text(get_text("admin_required", CONFIG.get('language')))
            return
        return func(update, context, *args, **kwargs)
    return wrapped

def auth_required(func):
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        if not context.user_data.get('role'):
            message = update.message or update.callback_query.message
            message.reply_text(get_text("auth_required", CONFIG.get('language')))
            return
        return func(update, context, *args, **kwargs)
    return wrapped

def config_required(section):
    def decorator(func):
        @wraps(func)
        def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
            is_configured = True
            conf_section = CONFIG.get(section.lower(), {})
            if section.lower() in ['radarr', 'sonarr']:
                if not all(conf_section.get(k) for k in ['url', 'api_key', 'root_folder_path']):
                    is_configured = False
            elif not all(conf_section.values()):
                 is_configured = False

            if not is_configured:
                message = update.message or update.callback_query.message
                message.reply_text(f"⚠️ The '{section}' section is not configured. The admin must use /setup.")
                return
            return func(update, context, *args, **kwargs)
        return wrapped
    return decorator


# --- API & Verification Logic Functions ---

def _api_get_request(url, params=None, headers=None):
    try:
        res = requests.get(url, params=params, headers=headers, timeout=20)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"GET request failed for {url}: {e}")
        return None

def _api_post_request(url, json_payload=None, headers=None):
    try:
        res = requests.post(url, json=json_payload, headers=headers, timeout=20)
        res.raise_for_status()
        if res.status_code in [200, 201] and res.content:
            return res.json()
        return {"status": "success", "code": res.status_code}
    except requests.exceptions.RequestException as e:
        logger.error(f"POST request failed for {url}: {e}")
        if e.response is not None:
            logger.error(f"API Response: {e.response.text}")
            try:
                return e.response.json()
            except json.JSONDecodeError:
                return {"error": e.response.text}
        return {"error": str(e)}

# --- Media Verification Cascade ---

def check_plex_library(title, year):
    plex_config = CONFIG.get('plex', {})
    if not all(plex_config.get(k) for k in ['url', 'token']): return None
    try:
        plex = PlexServer(plex_config['url'], plex_config['token'])
        results = plex.search(title)
        for item in results:
            if hasattr(item, 'year') and item.year == year and hasattr(item, 'media') and item.media:
                logger.info(f"Media '{title}' found on Plex.")
                return get_text('plex_found', CONFIG.get('language')).format(title=item.title, server_name=plex.friendlyName)
    except Exception as e:
        logger.error(f"Error checking Plex library: {e}")
    return None

def _search_tmdb(query, media_type):
    """Helper function to search TMDB."""
    lang = CONFIG.get('language')
    tmdb_key = CONFIG.get('tmdb', {}).get('api_key')
    if not tmdb_key:
        return [], "TMDB API key not configured."
    
    internal_media_type = 'tv' if media_type == 'show' else 'movie'
    url = f"https://api.themoviedb.org/3/search/{internal_media_type}"
    params = {'api_key': tmdb_key, 'query': query, 'language': lang, 'include_adult': 'false'}
    data = _api_get_request(url, params)
    
    if data and 'results' in data:
        return data['results'], None
    return [], f"No results found for '{query}'."

@config_required('TMDB')
def check_streaming_services(tmdb_id, media_type, title):
    tmdb_config = CONFIG.get('tmdb')
    region = tmdb_config.get('region', 'BR')
    lang = CONFIG.get('language')
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/watch/providers"
    params = {'api_key': tmdb_config['api_key']}
    data = _api_get_request(url, params)
    if not data or region not in data.get('results', {}): return None
    
    region_data = data['results'][region]
    provider_names = []
    for provider_type in ['flatrate', 'ads', 'free']:
        if provider_type in region_data:
            provider_names.extend([p['provider_name'] for p in region_data[provider_type]])
    
    if not provider_names: return None

    user_services = CONFIG.get("subscribed_services", [])
    available_on = set()
    for provider in provider_names:
        provider_lower = provider.lower()
        for code in user_services:
            if any(keyword in provider_lower for keyword in KEYWORD_MAP.get(code.lower(), ())):
                available_on.add(provider)
                break
    
    if available_on:
        services_str = ', '.join(sorted(list(available_on)))
        logger.info(f"Media '{title}' found on streaming services: {services_str}")
        return get_text('streaming_found', lang).format(title=title, services_str=services_str)
    return None

def check_overseerr(tmdb_id, media_type):
    ov_config = CONFIG.get('overseerr', {})
    if not all(ov_config.get(k) for k in ['url', 'api_key']): return None
    lang = CONFIG.get('language')
    internal_media_type = 'tv' if media_type == 'show' else 'movie'
    url = f"{ov_config['url'].rstrip('/')}/api/v1/request"
    headers = {'X-Api-Key': ov_config['api_key']}
    
    all_requests = _api_get_request(url, headers=headers)
    if all_requests and 'results' in all_requests:
        for req in all_requests['results']:
            if req['media'].get('tmdbId') == tmdb_id:
                logger.info(f"Media with TMDB ID {tmdb_id} has already been requested on Overseerr.")
                title = req['media'].get('title') or req['media'].get('name')
                return get_text('overseerr_found', lang).format(title=title)
    return None

def add_to_arr_service(media_info, service_name, is_4k=False):
    config = CONFIG.get(service_name.lower())
    lang = CONFIG.get('language')

    quality_key = 'quality_profile_id_4k' if is_4k else 'quality_profile_id'
    folder_key = 'root_folder_path_4k' if is_4k else 'root_folder_path'
    
    quality_profile_id = config.get(quality_key)
    root_folder_path = config.get(folder_key)

    if not quality_profile_id or not root_folder_path:
        return get_text('setup_4k_profile_not_configured', lang).format(service=service_name.capitalize())

    api_path = 'movie' if service_name == 'radarr' else 'series'
    url = f"{config['url'].rstrip('/')}/api/v3/{api_path}"
    headers = {'X-Api-Key': config['api_key']}
    
    payload = {
        "title": media_info['title'],
        "qualityProfileId": int(quality_profile_id),
        "rootFolderPath": root_folder_path,
        "monitored": True, "tmdbId": media_info['tmdb_id']
    }

    if service_name == 'radarr':
        payload['addOptions'] = {"searchForMovie": True}
    else: # Sonarr
        payload['languageProfileId'] = int(config.get('language_profile_id', 1))
        payload['addOptions'] = {"searchForMissingEpisodes": True}
        tmdb_key = CONFIG.get('tmdb', {}).get('api_key')
        if not tmdb_key: return "⚠️ TMDB API key not configured to fetch TVDB ID."
        ids_url = f"https://api.themoviedb.org/3/tv/{media_info['tmdb_id']}/external_ids?api_key={tmdb_key}"
        external_ids = _api_get_request(ids_url)
        if not external_ids or not external_ids.get('tvdb_id'):
            return f"❌ Could not find TVDB ID for '{media_info['title']}'. Cannot add to Sonarr."
        payload['tvdbId'] = external_ids['tvdb_id']

    all_items = _api_get_request(url, headers=headers)
    if all_items and any(item.get('tmdbId') == media_info['tmdb_id'] for item in all_items):
        return get_text('service_add_exists', lang).format(title=media_info['title'], service_name=service_name.capitalize())

    response = _api_post_request(url, json_payload=payload, headers=headers)
    if response and response.get('title') == media_info['title']:
        return get_text('service_add_success', lang).format(title=media_info['title'], service_name=service_name.capitalize())
    
    logger.error(f"Failed to add to {service_name.capitalize()}. Response: {response}")
    return get_text('service_add_fail', lang).format(title=media_info['title'], service_name=service_name.capitalize())


# --- Command Handlers ---

def start_cmd(update: Update, context: CallbackContext):
    """Greets the user and tells them how to authenticate."""
    global CONFIG
    CONFIG = load_config() # Reload config on start
    update.message.reply_text(get_text('start_message', CONFIG.get('language')))

def login_cmd(update: Update, context: CallbackContext) -> int:
    """Starts the login process for the admin."""
    lang = CONFIG.get('language')
    if context.user_data.get('role') == 'admin':
        update.message.reply_text(get_text('login_already_done', lang))
        return ConversationHandler.END

    if not os.getenv("BOT_USER") or not os.getenv("BOT_PASSWORD"):
        update.message.reply_text("🚨 CRITICAL ERROR: BOT_USER and BOT_PASSWORD variables are not set in the .env file.")
        return ConversationHandler.END

    if not CONFIG.get('admin_user_id') or update.effective_user.id == CONFIG.get('admin_user_id'):
        update.message.reply_text(get_text("login_prompt_user", lang))
        return AWAIT_LOGIN_USER
    else:
        update.message.reply_text(get_text('login_fail', lang))
        return ConversationHandler.END

def handle_login_user(update: Update, context: CallbackContext) -> int:
    """Handles the username step of the login process."""
    lang = CONFIG.get('language')
    context.user_data['login_username'] = update.message.text.strip()
    update.message.reply_text(get_text("login_prompt_pass", lang))
    return AWAIT_LOGIN_PASSWORD

def check_login_credentials(update: Update, context: CallbackContext) -> int:
    """Checks the admin credentials."""
    global CONFIG
    lang = CONFIG.get('language')
    password = update.message.text.strip()
    username = context.user_data.get('login_username')
    
    context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)

    if username == os.getenv("BOT_USER") and password == os.getenv("BOT_PASSWORD"):
        if not CONFIG.get('admin_user_id'):
            CONFIG['admin_user_id'] = update.effective_user.id
            save_config(CONFIG)
        
        context.user_data['role'] = 'admin'
        update.message.reply_text(get_text('login_success', lang))
        return ConversationHandler.END
    else:
        update.message.reply_text(get_text('login_fail', lang))
        return ConversationHandler.END

@auth_required
def logout_cmd(update: Update, context: CallbackContext):
    """Logs the current user out by clearing their session data."""
    context.user_data.clear()
    update.message.reply_text(get_text('logout_success', CONFIG.get('language')))

def auth_cmd(update: Update, context: CallbackContext) -> int:
    """Starts the friend authentication process."""
    if context.args:
        return _process_auth_code(update, context, context.args[0])
    
    update.message.reply_text(get_text("auth_prompt", CONFIG.get('language')))
    return AWAIT_FRIEND_CODE

def auth_receive_code(update: Update, context: CallbackContext) -> int:
    """Receives and processes the friend code from the user."""
    return _process_auth_code(update, context, update.message.text)

def _process_auth_code(update: Update, context: CallbackContext, code: str) -> int:
    """Internal logic to validate a friend code and grant access."""
    global CONFIG
    lang = CONFIG.get('language')
    friend_name = None

    active_codes = {c: data for c, data in CONFIG.get('friend_codes', {}).items() if datetime.fromisoformat(data['expires']) >= datetime.now()}
    if len(active_codes) != len(CONFIG.get('friend_codes', {})):
        CONFIG['friend_codes'] = active_codes
        save_config(CONFIG)

    if code in active_codes:
        friend_name = active_codes[code]['name']
        CONFIG.setdefault('friend_user_ids', {})[str(update.effective_user.id)] = friend_name
        del CONFIG['friend_codes'][code]
        context.user_data['role'] = 'friend'
        save_config(CONFIG)
        update.message.reply_text(get_text('auth_friend_code_accepted', lang))
    else:
        update.message.reply_text(get_text('auth_friend_code_invalid', lang))
    
    return ConversationHandler.END

def auth_cancel(update: Update, context: CallbackContext) -> int:
    """Cancels the authentication flow."""
    update.message.reply_text(get_text('auth_cancelled', CONFIG.get('language')))
    return ConversationHandler.END


@auth_required
def help_cmd(update: Update, context: CallbackContext):
    lang = CONFIG.get('language')
    if context.user_data.get('role') == 'admin':
        update.message.reply_text(get_text('help_admin', lang), parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text(get_text('help_friend', lang), parse_mode=ParseMode.MARKDOWN)

def _display_search_results(update: Update, context: CallbackContext, results: list, media_type: str, mode: str, is_4k: bool = False):
    lang = CONFIG.get('language')
    if not results:
        update.message.reply_text(get_text('no_results', lang).format(query=" ".join(context.args)))
        return

    context.user_data.update({'search_results': results, 'search_index': 0, 'search_media_type': media_type, 'search_mode': mode, 'is_4k': is_4k})
    _send_media_card(update, context)

def _send_media_card(update: Update, context: CallbackContext, chat_id=None, message_id=None):
    idx = context.user_data['search_index']
    results = context.user_data['search_results']
    item = results[idx]
    media_type = context.user_data['search_media_type']
    mode = context.user_data['search_mode']
    is_4k = context.user_data.get('is_4k', False)
    lang = CONFIG.get('language')
    user_role = context.user_data.get('role')

    is_movie = media_type == 'movie'
    title = item.get('title') if is_movie else item.get('name')
    release_date = item.get('release_date', item.get('first_air_date', ''))
    year = release_date.split('-')[0] if release_date else 'N/A'
    overview = item.get('overview', 'No synopsis available.')
    tmdb_id = item['id']
    poster_path = item.get('poster_path')
    image_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else f"https://placehold.co/500x750/1c1c1e/ffffff?text={requests.utils.quote(title)}"

    caption = f"*{title} ({year})*\n\n{overview[:700]}"
    
    buttons = []
    if mode == 'add':
        add_button_text = get_text('add_button_4k' if is_4k else 'add_button', lang)
        callback_suffix = f"_{'4k' if is_4k else 'std'}"
        if user_role == 'admin':
            buttons.append([InlineKeyboardButton(add_button_text, callback_data=f"add_{media_type}{callback_suffix}_{tmdb_id}")])
        else:
            buttons.append([InlineKeyboardButton(get_text('check_button', lang), callback_data=f"add_{media_type}_std_{tmdb_id}")])
    elif mode == 'check':
        buttons.append([InlineKeyboardButton(get_text('check_button', lang), callback_data=f"check_{media_type}_{tmdb_id}")])

    nav_buttons = []
    if idx > 0: nav_buttons.append(InlineKeyboardButton(get_text('nav_prev', lang), callback_data="nav_prev"))
    if idx < len(results) - 1: nav_buttons.append(InlineKeyboardButton(get_text('nav_next', lang), callback_data="nav_next"))
    
    # Add cancel button to all search results
    nav_buttons.append(InlineKeyboardButton(get_text('cancel_button', lang), callback_data="nav_cancel"))

    if nav_buttons: buttons.append(nav_buttons)

    keyboard = InlineKeyboardMarkup(buttons)
    effective_chat_id = chat_id or update.effective_chat.id
    media = InputMediaPhoto(media=image_url, caption=caption, parse_mode=ParseMode.MARKDOWN)

    if message_id:
        try:
            context.bot.edit_message_media(chat_id=effective_chat_id, message_id=message_id, media=media, reply_markup=keyboard)
        except Exception as e:
            if 'Message is not modified' not in str(e): logger.warning(f"Error editing media message: {e}")
    else:
        sent_message = context.bot.send_photo(effective_chat_id, photo=image_url, caption=caption, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        context.user_data['search_message_id'] = sent_message.message_id

def button_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    lang = CONFIG.get('language')

    if data == "nav_cancel":
        query.message.delete()
        context.bot.send_message(chat_id=query.message.chat_id, text=get_text('search_cancelled', lang))
        return

    if data.startswith("lang_"):
        set_language_callback(update, context)
        return

    if data.startswith("nav_"):
        context.user_data['search_index'] += 1 if data == 'nav_next' else -1
        _send_media_card(update, context, chat_id=query.message.chat_id, message_id=query.message.message_id)
        return

    query.message.delete()
    
    parts = data.split('_')
    action = parts[0]
    media_type = parts[1]
    is_4k = parts[2] == '4k' if action == 'add' else False
    tmdb_id_str = parts[-1]
    tmdb_id = int(tmdb_id_str)

    item = next((i for i in context.user_data.get('search_results', []) if i['id'] == tmdb_id), None)
    if not item:
        query.message.reply_text(get_text('error_media_details', lang))
        return

    title = item.get('title') or item.get('name')
    release_date = item.get('release_date') or item.get('first_air_date', '')
    year = int(release_date.split('-')[0]) if release_date else 0
    media_info = {'title': title, 'year': year, 'tmdb_id': tmdb_id, 'media_type': media_type}

    if action == 'add':
        perform_full_check_and_act(context, media_info, query.message.chat_id, update.effective_user.id, is_4k=is_4k)
    elif action == 'check':
        perform_simplified_check(context, media_info, query.message.chat_id)

def handle_request_approval(update: Update, context: CallbackContext):
    """Handles the admin's response to a friend's request."""
    query = update.callback_query
    query.answer()
    
    parts = query.data.split('_')
    action = parts[0]
    lang = CONFIG.get('language')
    
    if action == 'approve':
        quality, media_type, tmdb_id_str, friend_id_str = parts[1], parts[2], parts[3], parts[4]
        is_4k = quality == '4k'
        tmdb_id = int(tmdb_id_str)
        friend_id = int(friend_id_str)

        details_url = f"https://api.themoviedb.org/3/{'tv' if media_type == 'show' else 'movie'}/{tmdb_id}"
        params = {'api_key': CONFIG['tmdb']['api_key'], 'language': lang}
        item = _api_get_request(details_url, params)
        
        if not item:
            context.bot.send_message(chat_id=CONFIG['admin_user_id'], text="Error fetching media details to approve request.")
            return

        title = item.get('title') or item.get('name')
        release_date = item.get('release_date') or item.get('first_air_date', '')
        year = int(release_date.split('-')[0]) if release_date else 0
        media_info = {'title': title, 'year': year, 'tmdb_id': tmdb_id, 'media_type': media_type}
        
        service_name = 'radarr' if media_type == 'movie' else 'sonarr'
        add_result = add_to_arr_service(media_info, service_name, is_4k)
        
        query.edit_message_caption(caption=f"{query.message.caption}\n\n--- \n✅ Request Approved. Result: {add_result}", parse_mode=ParseMode.MARKDOWN)
        context.bot.send_message(chat_id=friend_id, text=get_text('request_approved_notification', lang).format(title=title))

    elif action == 'decline':
        media_type, tmdb_id_str, friend_id_str = parts[1], parts[2], parts[3]
        details_url = f"https://api.themoviedb.org/3/{'tv' if media_type == 'show' else 'movie'}/{tmdb_id_str}"
        params = {'api_key': CONFIG['tmdb']['api_key'], 'language': lang}
        item = _api_get_request(details_url, params)
        title = item.get('title') or item.get('name') if item else "your request"

        query.edit_message_caption(caption=f"{query.message.caption}\n\n--- \n❌ Request Declined.", parse_mode=ParseMode.MARKDOWN)
        context.bot.send_message(chat_id=int(friend_id_str), text=get_text('request_declined_notification', lang).format(title=title))

def perform_full_check_and_act(context: CallbackContext, media_info: dict, chat_id: int, user_id: int, is_4k: bool = False):
    title, year, tmdb_id = media_info['title'], media_info['year'], media_info['tmdb_id']
    media_type = 'tv' if media_info['media_type'] == 'show' else 'movie'
    lang = CONFIG.get('language')
    
    status_msg = context.bot.send_message(chat_id, get_text('checking_status', lang).format(title=title))

    if (plex_result := check_plex_library(title, year)):
        status_msg.edit_text(plex_result)
        return

    if (streaming_result := check_streaming_services(tmdb_id, media_type, title)):
        status_msg.edit_text(streaming_result)
        return

    if (overseerr_result := check_overseerr(tmdb_id, media_type)):
        status_msg.edit_text(overseerr_result)
        return
        
    status_msg.edit_text(get_text('media_unavailable', lang).format(title=title))
    
    if is_admin(user_id):
        add_result = add_to_arr_service(media_info, 'radarr' if media_type == 'movie' else 'sonarr', is_4k=is_4k)
        context.bot.send_message(chat_id, add_result)
    else:
        context.bot.send_message(chat_id, get_text('media_unavailable_friend', lang).format(title=title))
    
    status_msg.delete()

def check_arr_service(media_info, service_name):
    """Checks if a media item exists in Radarr or Sonarr."""
    config = CONFIG.get(service_name.lower())
    if not all(config.get(k) for k in ['url', 'api_key']): return None
    
    api_path = 'movie' if service_name == 'radarr' else 'series'
    url = f"{config['url'].rstrip('/')}/api/v3/{api_path}"
    headers = {'X-Api-Key': config['api_key']}
    
    all_items = _api_get_request(url, headers=headers)
    if all_items and any(item.get('tmdbId') == media_info['tmdb_id'] for item in all_items):
        return get_text('check_sonarr_radarr_found', CONFIG.get('language')).format(title=media_info['title'], service_name=service_name.capitalize())
    return None

def perform_simplified_check(context: CallbackContext, media_info: dict, chat_id: int):
    """Performs a simplified check on Plex and Radarr/Sonarr only."""
    title, year = media_info['title'], media_info['year']
    service_name = 'radarr' if media_info['media_type'] == 'movie' else 'sonarr'
    lang = CONFIG.get('language')

    status_msg = context.bot.send_message(chat_id, get_text('checking_status', lang).format(title=title))

    if (plex_result := check_plex_library(title, year)):
        status_msg.edit_text(plex_result)
        return
    
    if (arr_result := check_arr_service(media_info, service_name)):
        status_msg.edit_text(arr_result)
        return

    status_msg.edit_text(get_text('check_not_found', lang).format(title=title))

# --- Search Command Handlers ---

@auth_required
@config_required('TMDB')
def search_cmd(update: Update, context: CallbackContext, media_type: str, is_4k: bool = False):
    lang = CONFIG.get('language')
    if not context.args:
        command = f"{media_type}4k" if is_4k else media_type
        update.message.reply_text(get_text('provide_title', lang).format(command=command))
        return
    
    query = " ".join(context.args)
    results, error = _search_tmdb(query, media_type)
    
    if error:
        update.message.reply_text(error)
        return
    
    if results:
        _display_search_results(update, context, results, media_type, mode='add', is_4k=is_4k)
    else:
        update.message.reply_text(get_text('no_results', lang).format(query=query))

@auth_required
@config_required('TMDB')
def check_cmd(update: Update, context: CallbackContext):
    lang = CONFIG.get('language')
    if len(context.args) < 2:
        update.message.reply_text(get_text('check_usage', lang))
        return

    media_type, query = context.args[0].lower(), " ".join(context.args[1:])
    if media_type not in ['movie', 'show']:
        update.message.reply_text(get_text('check_usage', lang))
        return

    results, error = _search_tmdb(query, media_type)
    
    if error:
        update.message.reply_text(error)
        return

    if results:
        _display_search_results(update, context, results, media_type, mode='check')
    else:
        update.message.reply_text(get_text('no_results', lang).format(query=query))


@admin_required
def debug_cmd(update: Update, context: CallbackContext):
    if len(context.args) < 2:
        update.message.reply_text("Usage: /debug <movie|show> <title>")
        return

    media_type, query = context.args[0].lower(), " ".join(context.args[1:])
    lang = CONFIG.get('language')

    if media_type not in ['movie', 'show']:
        update.message.reply_text("The first argument must be 'movie' or 'show'.")
        return

    def report(key, **kwargs):
        context.bot.send_message(update.effective_chat.id, f"🐛 {get_text(key, lang).format(**kwargs)}")

    report('debug_start', query=query, media_type=media_type)
    report('debug_tmdb_search')
    
    results, error = _search_tmdb(query, media_type)
    
    if error:
        report("ERROR: " + error)
        return

    if not results:
        report('debug_tmdb_not_found', query=query)
        return

    item = results[0]
    title = item.get('title', item.get('name'))
    release_date = item.get('release_date', item.get('first_air_date', ''))
    year = int(release_date.split('-')[0]) if release_date else 0
    tmdb_id = item['id']
    report('debug_tmdb_found', title=title, year=year, tmdb_id=tmdb_id)
    
    report('debug_plex_check')
    if (plex_result := check_plex_library(title, year)): report('debug_plex_success', plex_result=plex_result)
    else: report('debug_plex_fail')

    report('debug_streaming_check')
    internal_media_type = 'tv' if media_type == 'show' else 'movie'
    if (streaming_result := check_streaming_services(tmdb_id, internal_media_type, title)): report('debug_streaming_success', streaming_result=streaming_result)
    else: report('debug_streaming_fail')

    report('debug_overseerr_check')
    if (overseerr_result := check_overseerr(tmdb_id, internal_media_type)): report('debug_overseerr_success', overseerr_result=overseerr_result)
    else: report('debug_overseerr_fail')

    report('debug_end')

def language_cmd(update: Update, context: CallbackContext):
    """Displays buttons for the user to choose the language."""
    lang = CONFIG.get('language')
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
        [InlineKeyboardButton("🇧🇷 Português", callback_data='lang_pt')],
        [InlineKeyboardButton("🇪🇸 Español", callback_data='lang_es')],
    ]
    update.message.reply_text(get_text('language_prompt', lang), reply_markup=InlineKeyboardMarkup(keyboard))

def set_language_callback(update: Update, context: CallbackContext):
    """Saves the new language choice."""
    global CONFIG
    query = update.callback_query
    new_lang = query.data.split('_')[1]
    
    CONFIG['language'] = new_lang
    save_config(CONFIG)
    
    lang_map = {'en': 'English', 'pt': 'Português', 'es': 'Español'}
    query.edit_message_text(get_text('language_set', new_lang).format(lang_name=lang_map[new_lang]))

def streaming_cmd(update: Update, context: CallbackContext):
    """Displays a list of available streaming service codes."""
    lang = CONFIG.get('language')
    message = get_text('streaming_list_header', lang)
    for code, names in KEYWORD_MAP.items():
        # Capitalize the first name for display
        display_name = names[0].title()
        message += f"`{code}` - {display_name}\n"
    
    update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


# --- Setup Conversation Handlers ---
def _send_setup_menu(update: Update, context: CallbackContext):
    """Sends the main setup menu."""
    lang = CONFIG.get('language')
    keyboard = [
        [
            InlineKeyboardButton(get_text('setup_section_plex', lang), callback_data='cfg_plex'),
            InlineKeyboardButton(get_text('setup_section_tmdb', lang), callback_data='cfg_tmdb')
        ],
        [
            InlineKeyboardButton(get_text('setup_section_radarr', lang), callback_data='cfg_radarr'),
            InlineKeyboardButton(get_text('setup_section_sonarr', lang), callback_data='cfg_sonarr')
        ],
        [
            InlineKeyboardButton(get_text('setup_section_overseerr', lang), callback_data='cfg_overseerr'),
            InlineKeyboardButton(get_text('setup_section_streaming', lang), callback_data='cfg_streaming')
        ],
        [InlineKeyboardButton(get_text('setup_all_button', lang), callback_data='cfg_all')],
        [InlineKeyboardButton(get_text('setup_save_exit_button', lang), callback_data='cfg_save')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = get_text('setup_menu_prompt', lang)
    
    if update.callback_query:
        query = update.callback_query
        query.answer()
        query.edit_message_text(text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text(text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

@admin_required
def setup_cmd(update: Update, context: CallbackContext) -> int:
    """Entry point for the setup conversation. Displays the menu."""
    context.user_data['setup_data'] = CONFIG.copy()
    _send_setup_menu(update, context)
    return SETUP_MENU

def setup_redirector(update: Update, context: CallbackContext) -> int:
    """Handles button presses from the setup menu and redirects to the correct state."""
    global CONFIG
    query = update.callback_query
    choice = query.data
    lang = CONFIG.get('language')
    
    prompt_map = {
        'cfg_plex': ("What is your Plex server's URL?", SETUP_PLEX_URL),
        'cfg_tmdb': ("What is your TMDB API key (v3)?", SETUP_TMDB_API_KEY),
        'cfg_streaming': ("Send your streaming service codes, comma-separated.", SETUP_SERVICES_CODES),
        'cfg_radarr': ("What is Radarr's URL?", SETUP_RADARR_URL),
        'cfg_sonarr': ("What is Sonarr's URL?", SETUP_SONARR_URL),
        'cfg_overseerr': ("What is Overseerr's URL?", SETUP_OVERSEERR_URL),
        'cfg_all': ("Starting full setup...\n\nFirst, Plex. What is your server's URL?", SETUP_PLEX_URL)
    }

    if choice == 'cfg_save':
        CONFIG = context.user_data['setup_data']
        if save_config(CONFIG):
            query.edit_message_text(get_text('setup_saved', lang))
        else:
            query.edit_message_text(get_text('setup_error_saving', lang))
        context.user_data.pop('setup_data', None)
        context.user_data.pop('setup_mode', None)
        return ConversationHandler.END

    if choice in prompt_map:
        prompt, next_state = prompt_map[choice]
        context.user_data['setup_mode'] = 'all' if choice == 'cfg_all' else 'individual'
        query.edit_message_text(text=prompt)
        return next_state
    
    return SETUP_MENU

def _return_to_menu_or_continue(update, context, next_state_for_all_mode, success_message):
    """Helper to decide whether to continue the full setup or return to the menu."""
    if context.user_data.get('setup_mode') == 'all':
        update.message.reply_text(success_message)
        return next_state_for_all_mode
    else:
        update.message.reply_text(f"✅ {success_message.split('!')[0]}!")
        _send_setup_menu(update, context)
        return SETUP_MENU

def setup_plex_url(update: Update, context: CallbackContext):
    context.user_data['setup_data'].setdefault('plex', {})['url'] = update.message.text.strip()
    update.message.reply_text("What is your Plex Token (X-Plex-Token)?")
    return SETUP_PLEX_TOKEN

def setup_plex_token(update: Update, context: CallbackContext):
    context.user_data['setup_data']['plex']['token'] = update.message.text.strip()
    return _return_to_menu_or_continue(update, context, SETUP_TMDB_API_KEY, "Plex configured!\n\nNow, for TMDB. What is your API key (v3)?")

def setup_tmdb_api_key(update, context):
    context.user_data['setup_data'].setdefault('tmdb', {})['api_key'] = update.message.text.strip()
    update.message.reply_text("What is your streaming region? (e.g., US, BR, PT)")
    return SETUP_TMDB_REGION

def setup_tmdb_region(update, context):
    context.user_data['setup_data']['tmdb']['region'] = update.message.text.strip().upper()
    return _return_to_menu_or_continue(update, context, SETUP_SERVICES_CODES, "TMDB configured!\n\nWhich streaming services do you subscribe to?")

def setup_services_codes(update, context):
    context.user_data['setup_data']['subscribed_services'] = [c.strip().lower() for c in update.message.text.split(',')]
    return _return_to_menu_or_continue(update, context, SETUP_RADARR_URL, "Services set!\n\nNow for Radarr. What is the URL?")

def setup_radarr_url(update, context):
    context.user_data['setup_data'].setdefault('radarr', {})['url'] = update.message.text.strip()
    update.message.reply_text("What is the Radarr API Key?")
    return SETUP_RADARR_API_KEY

def setup_radarr_api_key(update, context):
    context.user_data['setup_data']['radarr']['api_key'] = update.message.text.strip()
    update.message.reply_text("What is the Radarr Quality Profile ID?")
    return SETUP_RADARR_QUALITY_ID

def setup_radarr_quality_id(update, context):
    context.user_data['setup_data']['radarr']['quality_profile_id'] = update.message.text.strip()
    update.message.reply_text("What is the Radarr Root Folder Path?")
    return SETUP_RADARR_ROOT_FOLDER

def setup_radarr_root_folder(update, context):
    context.user_data['setup_data']['radarr']['root_folder_path'] = update.message.text.strip()
    update.message.reply_text(get_text('setup_ask_4k', CONFIG.get('language')).format(service='Radarr'))
    return AWAIT_RADARR_4K_CHOICE

def await_radarr_4k_choice(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    if text in ['yes', 'y', 'sim', 's']:
        update.message.reply_text(get_text('setup_4k_quality_prompt', CONFIG.get('language')).format(service='Radarr'))
        return SETUP_RADARR_QUALITY_ID_4K
    else:
        # Skip 4K config for Radarr
        context.user_data['setup_data']['radarr']['quality_profile_id_4k'] = ""
        context.user_data['setup_data']['radarr']['root_folder_path_4k'] = ""
        return _return_to_menu_or_continue(update, context, SETUP_SONARR_URL, "Radarr configured!\n\nNow for Sonarr. What is the URL?")

def setup_radarr_quality_id_4k(update, context):
    context.user_data['setup_data']['radarr']['quality_profile_id_4k'] = update.message.text.strip()
    update.message.reply_text(get_text('setup_4k_folder_prompt', CONFIG.get('language')).format(service='Radarr'))
    return SETUP_RADARR_ROOT_FOLDER_4K

def setup_radarr_root_folder_4k(update, context):
    context.user_data['setup_data']['radarr']['root_folder_path_4k'] = update.message.text.strip()
    return _return_to_menu_or_continue(update, context, SETUP_SONARR_URL, "Radarr configured!\n\nNow for Sonarr. What is the URL?")

def setup_sonarr_url(update, context):
    context.user_data['setup_data'].setdefault('sonarr', {})['url'] = update.message.text.strip()
    update.message.reply_text("What is the Sonarr API Key?")
    return SETUP_SONARR_API_KEY

def setup_sonarr_api_key(update, context):
    context.user_data['setup_data']['sonarr']['api_key'] = update.message.text.strip()
    update.message.reply_text("What is the Sonarr Quality Profile ID?")
    return SETUP_SONARR_QUALITY_ID

def setup_sonarr_quality_id(update, context):
    context.user_data['setup_data']['sonarr']['quality_profile_id'] = update.message.text.strip()
    update.message.reply_text("What is the Sonarr Language Profile ID?")
    return SETUP_SONARR_LANG_ID

def setup_sonarr_lang_id(update, context):
    context.user_data['setup_data']['sonarr']['language_profile_id'] = update.message.text.strip()
    update.message.reply_text("What is the Sonarr Root Folder Path?")
    return SETUP_SONARR_ROOT_FOLDER

def setup_sonarr_root_folder(update, context):
    context.user_data['setup_data']['sonarr']['root_folder_path'] = update.message.text.strip()
    update.message.reply_text(get_text('setup_ask_4k', CONFIG.get('language')).format(service='Sonarr'))
    return AWAIT_SONARR_4K_CHOICE

def await_sonarr_4k_choice(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    if text in ['yes', 'y', 'sim', 's']:
        update.message.reply_text(get_text('setup_4k_quality_prompt', CONFIG.get('language')).format(service='Sonarr'))
        return SETUP_SONARR_QUALITY_ID_4K
    else:
        # Skip 4K config for Sonarr
        context.user_data['setup_data']['sonarr']['quality_profile_id_4k'] = ""
        context.user_data['setup_data']['sonarr']['root_folder_path_4k'] = ""
        return _return_to_menu_or_continue(update, context, SETUP_OVERSEERR_URL, "Sonarr configured!\n\nFinally, Overseerr. What is the URL?")

def setup_sonarr_quality_id_4k(update, context):
    context.user_data['setup_data']['sonarr']['quality_profile_id_4k'] = update.message.text.strip()
    update.message.reply_text(get_text('setup_4k_folder_prompt', CONFIG.get('language')).format(service='Sonarr'))
    return SETUP_SONARR_ROOT_FOLDER_4K

def setup_sonarr_root_folder_4k(update, context):
    context.user_data['setup_data']['sonarr']['root_folder_path_4k'] = update.message.text.strip()
    return _return_to_menu_or_continue(update, context, SETUP_OVERSEERR_URL, "Sonarr configured!\n\nFinally, Overseerr. What is the URL?")


def setup_overseerr_url(update, context):
    context.user_data['setup_data'].setdefault('overseerr', {})['url'] = update.message.text.strip()
    update.message.reply_text("What is the Overseerr API Key?")
    return SETUP_OVERSEERR_API_KEY

def setup_overseerr_api_key(update, context):
    global CONFIG
    context.user_data['setup_data']['overseerr']['api_key'] = update.message.text.strip()
    update.message.reply_text("✅ Overseerr configured!")
    
    CONFIG = context.user_data['setup_data']
    if save_config(CONFIG):
        update.message.reply_text(get_text('setup_saved', CONFIG.get('language')))
    else:
        update.message.reply_text(get_text('setup_error_saving', CONFIG.get('language')))
    context.user_data.pop('setup_data', None)
    context.user_data.pop('setup_mode', None)
    return ConversationHandler.END

def cancel_setup(update: Update, context: CallbackContext) -> int:
    # Clear only setup-related data, preserving login state
    if 'setup_data' in context.user_data:
        del context.user_data['setup_data']
    if 'setup_mode' in context.user_data:
        del context.user_data['setup_mode']
        
    update.message.reply_text(get_text('setup_cancelled', CONFIG.get('language')))
    return ConversationHandler.END


# --- Friends Management Handlers ---

def _get_friends_menu(lang: str):
    """Generates the keyboard for the friends menu."""
    keyboard = [
        [InlineKeyboardButton(get_text('friends_button_add', lang), callback_data='friend_add')],
        [InlineKeyboardButton(get_text('friends_button_remove', lang), callback_data='friend_remove')],
        [InlineKeyboardButton(get_text('friends_button_list', lang), callback_data='friend_list')],
        [InlineKeyboardButton(get_text('friends_button_back', lang), callback_data='friend_back')],
    ]
    return InlineKeyboardMarkup(keyboard)

@admin_required
def friends_cmd(update: Update, context: CallbackContext) -> int:
    """Entry point for the friends management conversation."""
    lang = CONFIG.get('language')
    update.message.reply_text(
        get_text('friends_menu_prompt', lang),
        reply_markup=_get_friends_menu(lang),
        parse_mode=ParseMode.MARKDOWN
    )
    return FRIENDS_MENU

def friends_menu_logic(update: Update, context: CallbackContext) -> int:
    """Handles button presses from the main friends menu."""
    query = update.callback_query
    query.answer()
    action = query.data
    lang = CONFIG.get('language')

    if action == 'friend_add':
        query.edit_message_text(get_text('friends_add_prompt', lang))
        return AWAIT_FRIEND_NAME_TO_ADD
    
    if action == 'friend_list':
        friends = CONFIG.get('friend_user_ids', {})
        if not friends:
            query.edit_message_text(get_text('friends_no_friends', lang), reply_markup=_get_friends_menu(lang))
            return FRIENDS_MENU
        
        message = get_text('friends_list_title', lang) + "\n\n"
        message += "\n".join([get_text('friends_list_format', lang).format(name=name) for name in friends.values()])
        query.edit_message_text(message, reply_markup=_get_friends_menu(lang))
        return FRIENDS_MENU
        
    if action == 'friend_remove':
        friends = CONFIG.get('friend_user_ids', {})
        if not friends:
            query.edit_message_text(get_text('friends_no_friends_to_remove', lang), reply_markup=_get_friends_menu(lang))
            return FRIENDS_MENU
        
        keyboard = [[InlineKeyboardButton(name, callback_data=f"del_friend_{user_id}")] for user_id, name in friends.items()]
        keyboard.append([InlineKeyboardButton(get_text('friends_button_back', lang), callback_data='friend_back_to_menu')])
        query.edit_message_text(get_text('friends_remove_prompt', lang), reply_markup=InlineKeyboardMarkup(keyboard))
        return AWAIT_FRIEND_TO_REMOVE
        
    if action == 'friend_back':
        query.edit_message_text("Exited friends menu.")
        return ConversationHandler.END

    return FRIENDS_MENU

def add_friend_get_name(update: Update, context: CallbackContext) -> int:
    """Receives the name for a new friend and generates their code."""
    global CONFIG
    lang = CONFIG.get('language')
    name = update.message.text.strip()
    code = secrets.token_hex(8)
    expires = (datetime.now() + timedelta(days=1)).isoformat()
    
    CONFIG.setdefault('friend_codes', {})[code] = {'name': name, 'expires': expires}
    save_config(CONFIG)
    
    update.message.reply_text(get_text('new_friend_code', lang).format(name=name, code=code), parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

def remove_friend_confirm(update: Update, context: CallbackContext) -> int:
    """Removes a selected friend from the config."""
    global CONFIG
    query = update.callback_query
    query.answer()
    lang = CONFIG.get('language')
    
    if query.data == 'friend_back_to_menu':
        query.edit_message_text(get_text('friends_menu_prompt', lang), reply_markup=_get_friends_menu(lang), parse_mode=ParseMode.MARKDOWN)
        return FRIENDS_MENU

    user_id_to_remove = query.data.split('_')[-1]
    
    if user_id_to_remove in CONFIG.get('friend_user_ids', {}):
        removed_name = CONFIG['friend_user_ids'].pop(user_id_to_remove)
        save_config(CONFIG)
        query.edit_message_text(get_text('friends_friend_removed', lang).format(name=removed_name))
    
    # Go back to the main friends menu
    context.bot.send_message(
        chat_id=query.message.chat_id,
        text=get_text('friends_menu_prompt', lang),
        reply_markup=_get_friends_menu(lang),
        parse_mode=ParseMode.MARKDOWN
    )
    return FRIENDS_MENU

def unauthenticated_handler(update: Update, context: CallbackContext):
    """Handles any message from a user who is not logged in."""
    # This check is vital. It ensures this handler only acts on users who are not logged in.
    if not context.user_data.get('role'):
        update.message.reply_text(get_text("unauthenticated_message", 'en')) # Always in English

# --- Main Function ---
def main() -> None:
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.critical("BOT_TOKEN environment variable not set.")
        return

    # Initialize the updater without persistence to ensure sessions are not saved.
    updater = Updater(bot_token, persistence=None, use_context=True)
    dispatcher = updater.dispatcher
    
    # Initialize the friend request module with necessary functions from the main bot
    friend_requests.initialize_request_module(_search_tmdb, check_plex_library, get_text)

    # Pass the global CONFIG to the friend_requests module
    dispatcher.bot_data['config'] = CONFIG
    
    login_conv = ConversationHandler(
        entry_points=[CommandHandler('login', login_cmd)],
        states={
            AWAIT_LOGIN_USER: [MessageHandler(Filters.text & ~Filters.command, handle_login_user)],
            AWAIT_LOGIN_PASSWORD: [MessageHandler(Filters.text & ~Filters.command, check_login_credentials)],
        },
        fallbacks=[CommandHandler('cancel', cancel_setup)],
    )

    auth_conv = ConversationHandler(
        entry_points=[CommandHandler('auth', auth_cmd)],
        states={
            AWAIT_FRIEND_CODE: [MessageHandler(Filters.text & ~Filters.command, auth_receive_code)]
        },
        fallbacks=[CommandHandler('cancel', auth_cancel)]
    )
    
    setup_conv = ConversationHandler(
        entry_points=[CommandHandler('setup', setup_cmd)],
        states={
            SETUP_MENU: [CallbackQueryHandler(setup_redirector, pattern='^cfg_')],
            SETUP_PLEX_URL: [MessageHandler(Filters.text & ~Filters.command, setup_plex_url)],
            SETUP_PLEX_TOKEN: [MessageHandler(Filters.text & ~Filters.command, setup_plex_token)],
            SETUP_TMDB_API_KEY: [MessageHandler(Filters.text & ~Filters.command, setup_tmdb_api_key)],
            SETUP_TMDB_REGION: [MessageHandler(Filters.text & ~Filters.command, setup_tmdb_region)],
            SETUP_SERVICES_CODES: [MessageHandler(Filters.text & ~Filters.command, setup_services_codes)],
            SETUP_RADARR_URL: [MessageHandler(Filters.text & ~Filters.command, setup_radarr_url)],
            SETUP_RADARR_API_KEY: [MessageHandler(Filters.text & ~Filters.command, setup_radarr_api_key)],
            SETUP_RADARR_QUALITY_ID: [MessageHandler(Filters.text & ~Filters.command, setup_radarr_quality_id)],
            SETUP_RADARR_ROOT_FOLDER: [MessageHandler(Filters.text & ~Filters.command, setup_radarr_root_folder)],
            AWAIT_RADARR_4K_CHOICE: [MessageHandler(Filters.text & ~Filters.command, await_radarr_4k_choice)],
            SETUP_RADARR_QUALITY_ID_4K: [MessageHandler(Filters.text & ~Filters.command, setup_radarr_quality_id_4k)],
            SETUP_RADARR_ROOT_FOLDER_4K: [MessageHandler(Filters.text & ~Filters.command, setup_radarr_root_folder_4k)],
            SETUP_SONARR_URL: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_url)],
            SETUP_SONARR_API_KEY: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_api_key)],
            SETUP_SONARR_QUALITY_ID: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_quality_id)],
            SETUP_SONARR_LANG_ID: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_lang_id)],
            SETUP_SONARR_ROOT_FOLDER: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_root_folder)],
            AWAIT_SONARR_4K_CHOICE: [MessageHandler(Filters.text & ~Filters.command, await_sonarr_4k_choice)],
            SETUP_SONARR_QUALITY_ID_4K: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_quality_id_4k)],
            SETUP_SONARR_ROOT_FOLDER_4K: [MessageHandler(Filters.text & ~Filters.command, setup_sonarr_root_folder_4k)],
            SETUP_OVERSEERR_URL: [MessageHandler(Filters.text & ~Filters.command, setup_overseerr_url)],
            SETUP_OVERSEERR_API_KEY: [MessageHandler(Filters.text & ~Filters.command, setup_overseerr_api_key)],
        },
        fallbacks=[CommandHandler('cancel', cancel_setup)],
    )
    
    friends_conv = ConversationHandler(
        entry_points=[CommandHandler('friends', friends_cmd)],
        states={
            FRIENDS_MENU: [CallbackQueryHandler(friends_menu_logic, pattern='^friend_')],
            AWAIT_FRIEND_NAME_TO_ADD: [MessageHandler(Filters.text & ~Filters.command, add_friend_get_name)],
            AWAIT_FRIEND_TO_REMOVE: [CallbackQueryHandler(remove_friend_confirm, pattern='^del_friend_|^friend_back_to_menu$')],
        },
        fallbacks=[CommandHandler('cancel', cancel_setup)]
    )

    dispatcher.add_handler(CommandHandler("start", start_cmd))
    dispatcher.add_handler(login_conv)
    dispatcher.add_handler(auth_conv)
    dispatcher.add_handler(CommandHandler("logout", logout_cmd))
    dispatcher.add_handler(setup_conv)
    dispatcher.add_handler(friends_conv)
    dispatcher.add_handler(CommandHandler("help", help_cmd))
    dispatcher.add_handler(CommandHandler("debug", debug_cmd))
    dispatcher.add_handler(CommandHandler("language", language_cmd))
    dispatcher.add_handler(CommandHandler("streaming", streaming_cmd))
    dispatcher.add_handler(CommandHandler("check", check_cmd))
    dispatcher.add_handler(CommandHandler("friendrequest", friend_requests.handle_friend_request))
    dispatcher.add_handler(CommandHandler("movie", lambda u, c: search_cmd(u, c, 'movie')))
    dispatcher.add_handler(CommandHandler("show", lambda u, c: search_cmd(u, c, 'show')))
    dispatcher.add_handler(CommandHandler("movie4k", lambda u, c: search_cmd(u, c, 'movie', is_4k=True)))
    dispatcher.add_handler(CommandHandler("show4k", lambda u, c: search_cmd(u, c, 'show', is_4k=True)))
    dispatcher.add_handler(CallbackQueryHandler(button_callback_handler, pattern="^(add|check|nav)_"))
    dispatcher.add_handler(CallbackQueryHandler(handle_request_approval, pattern="^(approve|decline)_"))
    dispatcher.add_handler(CallbackQueryHandler(set_language_callback, pattern="^lang_"))


    # This handler catches any message or command not handled above
    # It must be added last among the message/command handlers
    dispatcher.add_handler(MessageHandler(Filters.all, unauthenticated_handler))


    updater.start_polling()
    logger.info("Bot started and listening for commands...")
    updater.idle()

if __name__ == '__main__':
    main()

