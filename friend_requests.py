# friend_requests.py

from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackContext

# These will be initialized by the main bot
_search_tmdb = None
_check_plex_library = None
_get_text = None

REQUEST_LIMITS = {}
MAX_REQUESTS_PER_DAY = 3

def initialize_request_module(search_tmdb_func, check_plex_func, get_text_func):
    """Initializes the module with functions from the main bot."""
    global _search_tmdb, _check_plex_library, _get_text
    _search_tmdb = search_tmdb_func
    _check_plex_library = check_plex_func
    _get_text = get_text_func

def _check_rate_limit(user_id):
    """Checks if a user has exceeded their daily request limit."""
    now = datetime.now()
    # Clean up old user entries
    for uid in list(REQUEST_LIMITS.keys()):
        valid_requests = [req_time for req_time in REQUEST_LIMITS[uid] if now - req_time < timedelta(days=1)]
        if not valid_requests:
            del REQUEST_LIMITS[uid]
        else:
            REQUEST_LIMITS[uid] = valid_requests
            
    user_requests = REQUEST_LIMITS.get(user_id, [])
    
    if len(user_requests) >= MAX_REQUESTS_PER_DAY:
        return False
    return True

def handle_friend_request(update: Update, context: CallbackContext):
    """Handles the /friendrequest command initiated by a friend."""
    friend_user_id = update.effective_user.id
    # Access config from context.bot_data, set by the main bot
    config = context.bot_data.get('config', {})
    lang = config.get('language', 'en')

    if not _check_rate_limit(friend_user_id):
        update.message.reply_text(_get_text('request_limit_reached', lang))
        return

    if len(context.args) < 2:
        update.message.reply_text(_get_text('friendrequest_usage', lang))
        return

    media_type, query = context.args[0].lower(), " ".join(context.args[1:])

    if media_type not in ['movie', 'show']:
        update.message.reply_text(_get_text('friendrequest_usage', lang))
        return
        
    update.message.reply_text(_get_text('checking_status', lang).format(title=query))
    
    results, error = _search_tmdb(query, media_type)

    if error:
        update.message.reply_text(f"⚠️ Error: {error}")
        return
    if not results:
        update.message.reply_text(_get_text('no_results', lang).format(query=query))
        return
    
    item = results[0]
    is_movie = media_type == 'movie'
    title = item.get('title') if is_movie else item.get('name')
    release_date = item.get('release_date', item.get('first_air_date', ''))
    year = int(release_date.split('-')[0]) if release_date else 0
    tmdb_id = item['id']
    
    if _check_plex_library(title, year):
        update.message.reply_text(_get_text('request_already_in_library', lang).format(title=title))
        return

    admin_id = config.get('admin_user_id')
    if not admin_id:
        update.message.reply_text("Admin not configured. Cannot process request.")
        return

    REQUEST_LIMITS.setdefault(friend_user_id, []).append(datetime.now())

    callback_data_approve_std = f"approve_std_{media_type}_{tmdb_id}_{friend_user_id}"
    callback_data_approve_4k = f"approve_4k_{media_type}_{tmdb_id}_{friend_user_id}"
    callback_data_decline = f"decline_{media_type}_{tmdb_id}_{friend_user_id}"

    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=callback_data_approve_std),
            InlineKeyboardButton("✅ Accept 4K", callback_data=callback_data_approve_4k)
        ],
        [InlineKeyboardButton("❌ Decline", callback_data=callback_data_decline)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    friend_username = update.effective_user.first_name
    
    poster_path = item.get('poster_path')
    image_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
    
    caption = (
        f"📩 New Media Request from {friend_username}\n\n"
        f"*{title} ({year})*\n\n"
        f"{item.get('overview', 'No overview available.')[:400]}"
    )

    try:
        if image_url:
            context.bot.send_photo(
                chat_id=admin_id,
                photo=image_url,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            context.bot.send_message(
                chat_id=admin_id,
                text=caption,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        update.message.reply_text(_get_text('request_sent', lang).format(title=title))
    except Exception as e:
        logger.error(f"Failed to send request to admin: {e}")
        update.message.reply_text("An error occurred while sending your request to the admin.")

