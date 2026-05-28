import os
import sys
import random
from datetime import datetime, timedelta
import telebot
from telebot import types
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Colors for terminal logs
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

print(f"{Colors.HEADER}=== Naino Academy Telegram Verification Bot ==={Colors.ENDC}")

# 1. Initialize Firebase Admin SDK
db = None
try:
    possible_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../naino app backend/naino-app-firebase-adminsdk-fbsvc-57f4cd3af4.json')),
        os.path.abspath(os.path.join(os.path.dirname(__file__), './naino-app-firebase-adminsdk-fbsvc-57f4cd3af4.json')),
    ]
    
    cred_file = None
    for p in possible_paths:
        if os.path.exists(p):
            cred_file = p
            break
            
    if cred_file:
        print(f"{Colors.OKBLUE}[Firebase] Loading service account from: {cred_file}{Colors.ENDC}")
        cred = credentials.Certificate(cred_file)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print(f"{Colors.OKGREEN}[Firebase] Admin SDK initialized successfully.{Colors.ENDC}")
    else:
        firebase_sa_env = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
        if firebase_sa_env:
            import json
            import base64
            print(f"{Colors.OKBLUE}[Firebase] Loading service account from environment variable.{Colors.ENDC}")
            firebase_sa_env = firebase_sa_env.strip()
            if (firebase_sa_env.startswith("'") and firebase_sa_env.endswith("'")) or (firebase_sa_env.startswith('"') and firebase_sa_env.endswith('"')):
                firebase_sa_env = firebase_sa_env[1:-1].strip()
            
            if not firebase_sa_env.startswith('{'):
                try:
                    firebase_sa_env = base64.b64decode(firebase_sa_env).decode('utf-8')
                except Exception as b64_err:
                    print(f"{Colors.WARNING}[Firebase] Base64 decode failed: {b64_err}. Trying raw JSON...{Colors.ENDC}")
                    
            sa_info = json.loads(firebase_sa_env)
            cred = credentials.Certificate(sa_info)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print(f"{Colors.OKGREEN}[Firebase] Admin SDK initialized successfully.{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}[Firebase] Service account JSON file not found in possible locations.{Colors.ENDC}")
            sys.exit(1)
except Exception as e:
    print(f"{Colors.FAIL}[Firebase] Initialization failed: {e}{Colors.ENDC}")
    sys.exit(1)

# 2. Initialize Telegram Bot
token = os.environ.get('TELEGRAM_BOT_TOKEN')
if not token or token == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
    print(f"{Colors.WARNING}[Telegram] TELEGRAM_BOT_TOKEN is not set in .env! Please configure your token.{Colors.ENDC}")
    sys.exit(1)

bot = telebot.TeleBot(token)
print(f"{Colors.OKGREEN}[Telegram] Bot client initialized successfully.{Colors.ENDC}")


# --- Markdown Escaping Helper ---
def escape_markdown(text):
    """Escapes Markdown special characters to prevent TeleBot ApiTelegramException"""
    if not text:
        return ""
    for char in ['_', '*', '`', '[']:
        text = text.replace(char, f"\\{char}")
    return text


# --- Loading Overlay Helpers ---
def show_loader(chat_id):
    """Sends a loading GIF or text loader and triggers chat typing action for immediate feedback"""
    try:
        bot.send_chat_action(chat_id, 'typing')
    except:
        pass
        
    gif_url = os.environ.get('LOADING_GIF_URL', '')
    if gif_url:
        try:
            loader = bot.send_animation(
                chat_id, 
                gif_url, 
                caption="⏳ *𝗣𝗥𝗢𝗖𝗘𝗦𝗦𝗜𝗡𝗚...* _Please wait..._", 
                parse_mode="Markdown"
            )
            return ('gif', loader.message_id)
        except Exception as e:
            print(f"[Loader] Failed to send GIF: {e}")
            
    loader = bot.send_message(
        chat_id, 
        "⚡ *𝗣𝗥𝗢𝗖𝗘𝗦𝗦𝗜𝗡𝗚...*\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬\n"
        "⏳ _Connecting to database. Please wait..._", 
        parse_mode="Markdown"
    )
    return ('text', loader.message_id)


def hide_loader(chat_id, loader_info):
    """Deletes the temporary loader message/animation"""
    if not loader_info:
        return
    try:
        loader_type, msg_id = loader_info
        bot.delete_message(chat_id, msg_id)
    except Exception as e:
        print(f"[Loader] Failed to delete loader message: {e}")


# --- Admin Verification Helper ---
def is_admin(from_user):
    """Checks if a user is an administrator based on ID or username in .env"""
    user_id = str(from_user.id)
    sender_username = (from_user.username or "").lower().replace('@', '').strip()
    
    admin_ids_str = os.environ.get('ADMIN_IDS', '')
    if admin_ids_str:
        admin_ids = [i.strip() for i in admin_ids_str.split(',') if i.strip()]
        if user_id in admin_ids:
            return True
            
    # Fallback to username checking
    admin1 = os.environ.get('ADMIN_1_USERNAME', '').lower().replace('@', '').strip()
    admin2 = os.environ.get('ADMIN_2_USERNAME', '').lower().replace('@', '').strip()
    
    if admin1 and sender_username == admin1:
        return True
    if admin2 and sender_username == admin2:
        return True
        
    return False


# --- Premium Keyboard Markups (Matches Screenshot) ---
MAIN_MENU_TEXT = (
    "🎓 *NAINO ACADEMY* ⚡\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "🏠 *MAIN MENU*\n\n"
    "👇 *Choose an option below* 👇"
)

def edit_message_safe(chat_id, message_id, text, reply_markup=None, parse_mode="Markdown"):
    """Safely edits a telegram message, ignoring 'message is not modified' errors"""
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" in str(e):
            pass
        else:
            print(f"[Telegram] Failed to edit message: {e}")

def get_main_keyboard(is_user_admin=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_demo = types.InlineKeyboardButton("✨ Generate Key", callback_data="menu_free_key")
    btn_prof = types.InlineKeyboardButton("👤 Profile / Status", callback_data="menu_profile")
    btn_down = types.InlineKeyboardButton("📥 App Download", callback_data="menu_download")
    btn_supp = types.InlineKeyboardButton("🆘 Support", callback_data="menu_support")
    
    markup.add(btn_demo, btn_prof)
    markup.add(btn_down, btn_supp)
    
    if is_user_admin:
        btn_gen = types.InlineKeyboardButton("🔑 Key Generator (Admin)", callback_data="menu_key_generator")
        markup.add(btn_gen)
        
    return markup


def get_plan_selector_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_free = types.InlineKeyboardButton("🆓 Free Account (10 Years)", callback_data="gen_plan_free")
    btn_prem_1 = types.InlineKeyboardButton("⭐ Silver Plan (1 Month)", callback_data="gen_plan_premium_1")
    btn_prem_12 = types.InlineKeyboardButton("👑 Gold Plan (1 Year)", callback_data="gen_plan_premium_12")
    btn_back = types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
    markup.add(btn_free, btn_prem_1, btn_prem_12, btn_back)
    return markup


def get_profile_keyboard(has_key=False, key_code=None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    if has_key and key_code:
        markup.add(types.InlineKeyboardButton("🔄 Reset Device Binding", callback_data=f"reset_confirm_{key_code}"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main"))
    return markup


def get_reset_confirm_keyboard(key_code):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_yes = types.InlineKeyboardButton("✅ Yes, Reset", callback_data=f"reset_execute_{key_code}")
    btn_no = types.InlineKeyboardButton("❌ Cancel", callback_data="menu_profile")
    markup.add(btn_yes, btn_no)
    return markup


def get_back_to_main_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main"))
    return markup


def get_support_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    admin_username1 = os.environ.get('ADMIN_1_USERNAME', '').strip().replace('@', '')
    admin_username2 = os.environ.get('ADMIN_2_USERNAME', '').strip().replace('@', '')
    dev_username = os.environ.get('DEVELOPER_USERNAME', '').strip().replace('@', '')
    
    if admin_username1:
        markup.add(types.InlineKeyboardButton("👑 Admin 1", url=f"https://t.me/{admin_username1}"))
    if admin_username2:
        markup.add(types.InlineKeyboardButton("👸Admin 2", url=f"https://t.me/{admin_username2}"))
    if dev_username:
        markup.add(types.InlineKeyboardButton("🧑‍💻Developer", url=f"https://t.me/{dev_username}"))
        
    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main"))
    return markup


# --- Membership Helpers ---
def check_membership(from_user):
    """Verifies that user has joined all groups/channels listed in REQUIRED_CHAT_IDS (Admins bypass)"""
    if is_admin(from_user):
        return True

    required_ids_str = os.environ.get('REQUIRED_CHAT_IDS', '')
    if not required_ids_str:
        return True
        
    chat_ids = [int(i.strip()) for i in required_ids_str.split(',') if i.strip()]
    if not chat_ids:
        return True
        
    user_id = from_user.id
    for chat_id in chat_ids:
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                return False
        except Exception as e:
            # Silent fallback / friendly log to avoid console clutter
            print(f"[Membership Check] Note: Chat {chat_id} is not accessible. Make sure the bot is added as Admin in the chat.")
            pass
    return True


def send_membership_warning(chat_id):
    links_str = os.environ.get('REQUIRED_INVITE_LINKS', '')
    links_list = [l.strip() for l in links_str.split(',') if l.strip()]
    
    msg_text = (
        "⚠️ *𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗲𝗻𝗶𝗲𝗱!*\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
        "To use this bot, you must first join our channels and groups:\n\n"
    )
    for idx, link in enumerate(links_list, 1):
        msg_text += f"{idx}. {link}\n"
    
    msg_text += "\nAfter joining, click the verification button below or send `/start` to verify."
    
    markup = types.InlineKeyboardMarkup()
    btn_check = types.InlineKeyboardButton("🔄 𝗩𝗲𝗿𝗶𝗳𝘆 𝗝𝗼𝗶𝗻", callback_data="verify_membership")
    markup.add(btn_check)
    
    bot.send_message(chat_id, msg_text, parse_mode="Markdown", reply_markup=markup)


# --- Core Action Logic ---
def verify_code(message, code: str):
    """Verifies a 4-digit verification code and binds the new device ID"""
    sender_id = str(message.from_user.id)
    sender_username = message.from_user.username or ""
    
    loader = show_loader(message.chat.id)
    
    try:
        keys_ref = db.collection('access_keys')
        query_ref = keys_ref.where('pendingVerificationCode', '==', code).limit(1)
        docs = query_ref.get()
        
        hide_loader(message.chat.id, loader)
        
        if not docs:
            bot.reply_to(
                message,
                "❌ *𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗼𝗿 𝗘𝘅𝗽𝗶𝗿𝗲𝗱 𝗖𝗼𝗱𝗲!*\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Please check the 4-digit code shown in the Naino Academy app.\n"
                "Note that codes expire after 5 minutes.",
                parse_mode="Markdown"
            )
            return
            
        doc = docs[0]
        data = doc.to_dict()
        key_id = doc.id
        registered_telegram_id = str(data.get('telegramId', '')).strip()
        pending_device_id = data.get('pendingDeviceId')
        
        # Verify account match (Admins bypass verification check)
        match_success = False
        clean_reg_tg = registered_telegram_id.lower().replace('@', '')
        clean_sender_uname = sender_username.lower().replace('@', '')
        
        if is_admin(message.from_user):
            match_success = True
        elif registered_telegram_id == sender_id:
            match_success = True
        elif clean_reg_tg and clean_reg_tg == clean_sender_uname:
            match_success = True
            
        if not match_success:
            bot.reply_to(
                message,
                f"❌ *𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱!*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"This verification code is for a key registered to a different Telegram account:\n"
                f"`{escape_markdown(registered_telegram_id)}`\n\n"
                f"Please send this code from your *registered Telegram account* or contact the Admin to update your profile.",
                parse_mode="Markdown"
            )
            return
            
        # Update device ID and clear verification fields
        doc_ref = keys_ref.document(key_id)
        doc_ref.update({
            'deviceId': pending_device_id,
            'pendingVerificationCode': None,
            'pendingDeviceId': None,
            'pendingVerificationCreatedAt': None
        })
        
        bot.reply_to(
            message,
            "✅ *𝗩𝗲𝗿𝗶𝗳𝗶𝗰𝗮𝘁𝗶𝗼𝗻 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your new device has been authorized successfully.\n"
            "Your Naino Academy app will unlock automatically in a few seconds.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(is_admin(message.from_user))
        )
        print(f"{Colors.OKGREEN}[Result] Success! Key {key_id} bound to device {pending_device_id}.{Colors.ENDC}")
        
    except Exception as e:
        hide_loader(message.chat.id, loader)
        print(f"{Colors.FAIL}[Error] Database operation failed: {e}{Colors.ENDC}")
        bot.reply_to(message, "❌ *𝗜𝗻𝘁𝗲𝗿𝗻𝗮𝗹 𝗘𝗿𝗿𝗼𝗿:* Failed to update database. Please try again.")


def reset_key_manually(message, key: str):
    """Resets a 6-digit key's device binding directly, if telegram ID matches or requester is Admin"""
    sender_id = str(message.from_user.id)
    sender_username = message.from_user.username or ""
    
    loader = show_loader(message.chat.id)
    
    try:
        doc_ref = db.collection('access_keys').document(key)
        doc_snap = doc_ref.get()
        
        hide_loader(message.chat.id, loader)
        
        if not doc_snap.exists:
            bot.reply_to(
                message,
                "❌ *𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗔𝗰𝗰𝗲𝘀𝘀 𝗞𝗲𝘆!*\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Please verify that your 6-digit key is correct.",
                parse_mode="Markdown"
            )
            return
            
        data = doc_snap.data()
        registered_telegram_id = str(data.get('telegramId', '')).strip()
        
        # Verify account match (Admins bypass verification check)
        match_success = False
        clean_reg_tg = registered_telegram_id.lower().replace('@', '')
        clean_sender_uname = sender_username.lower().replace('@', '')
        
        if is_admin(message.from_user):
            match_success = True
        elif registered_telegram_id == sender_id:
            match_success = True
        elif clean_reg_tg and clean_reg_tg == clean_sender_uname:
            match_success = True
            
        if not match_success:
            bot.reply_to(
                message,
                f"❌ *𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱!*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"This key is registered to a different Telegram account:\n"
                f"`{escape_markdown(registered_telegram_id)}`\n\n"
                f"You cannot reset device bindings of keys that are not registered to your account.",
                parse_mode="Markdown"
            )
            return
            
        # Update device ID (clear it)
        doc_ref.update({
            'deviceId': "",
            'pendingVerificationCode': None,
            'pendingDeviceId': None,
            'pendingVerificationCreatedAt': None
        })
        
        bot.reply_to(
            message,
            "✅ *Reset Successful!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your access key device binding has been completely cleared.\n"
            "You can now log in on any device.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(is_admin(message.from_user))
        )
        print(f"{Colors.OKGREEN}[Result] Manual reset successful for key {key}.{Colors.ENDC}")
        
    except Exception as e:
        hide_loader(message.chat.id, loader)
        print(f"{Colors.FAIL}[Error] Manual reset failed: {e}{Colors.ENDC}")
        bot.reply_to(message, "❌ *𝗜𝗻𝘁𝗲𝗿𝗻𝗮𝗹 𝗘𝗿𝗿𝗼𝗿:* Failed to reset key. Please try again.")


def generate_new_key(plan_type: str) -> tuple:
    """Generates a unique 6-digit key in Firestore and returns (key, expires_at_str, plan_name)"""
    keys_ref = db.collection('access_keys')
    
    new_key = ""
    while True:
        candidate = str(random.randint(100000, 999999))
        if not keys_ref.document(candidate).get().exists:
            new_key = candidate
            break
            
    now = datetime.utcnow()
    
    if plan_type == 'free':
        expires_at = now + timedelta(days=3652) # 10 years
        new_key_data = {
            'planId': 'free',
            'planName': 'Free Account',
            'createdAt': now.isoformat() + 'Z',
            'expiresAt': expires_at.isoformat() + 'Z',
            'status': 'active',
            'isPremium': False
        }
        plan_name = "Free Account (10 Years)"
    elif plan_type == 'premium_1':
        expires_at = now + timedelta(days=30)
        new_key_data = {
            'planId': 'silver',
            'planName': 'Silver Plan',
            'createdAt': now.isoformat() + 'Z',
            'expiresAt': expires_at.isoformat() + 'Z',
            'status': 'active',
            'isPremium': True,
            'plan': 'silver',
            'pendingRequest': {
                'status': 'approved',
                'plan': 'silver'
            }
        }
        plan_name = "Silver Plan (1 Month)"
    else: # premium_12 / gold
        expires_at = now + timedelta(days=365)
        new_key_data = {
            'planId': 'gold',
            'planName': 'Gold Plan',
            'createdAt': now.isoformat() + 'Z',
            'expiresAt': expires_at.isoformat() + 'Z',
            'status': 'active',
            'isPremium': True,
            'plan': 'gold',
            'pendingRequest': {
                'status': 'approved',
                'plan': 'gold'
            }
        }
        plan_name = "Gold Plan (1 Year)"
        
    keys_ref.document(new_key).set(new_key_data)
    
    expires_str = expires_at.strftime('%Y-%m-%d %H:%M UTC')
    return new_key, expires_str, plan_name


# --- Bot Event Handlers ---

# 1. Join Request Auto-Approver
@bot.chat_join_request_handler()
def handle_chat_join_request(message):
    try:
        bot.approve_chat_join_request(message.chat.id, message.from_user.id)
        print(f"{Colors.OKGREEN}[Join Request] Approved user {message.from_user.id} in chat {message.chat.id} ({message.chat.title}){Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}[Join Request] Failed to approve request: {e}{Colors.ENDC}")


# 2. Callback Query Handler for Menu Actions
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    # Check membership first (bypasses for admin)
    if not check_membership(call.from_user):
        bot.answer_callback_query(call.id, "❌ Verify membership first!", show_alert=True)
        send_membership_warning(call.message.chat.id)
        return
        
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Verify Join Callback
    if call.data == "verify_membership":
        bot.answer_callback_query(call.id, "⏳ Checking...")
        if check_membership(call.from_user):
            bot.answer_callback_query(call.id, "✅ Membership verified!")
            try:
                bot.delete_message(chat_id, message_id)
            except:
                pass
            bot.send_message(
                chat_id,
                MAIN_MENU_TEXT,
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(is_admin(call.from_user))
            )
        else:
            bot.answer_callback_query(call.id, "❌ You haven't joined all required chats yet!", show_alert=True)
            
    # Main Menu Callback
    elif call.data == "menu_main":
        bot.answer_callback_query(call.id)
        edit_message_safe(chat_id, message_id, MAIN_MENU_TEXT, get_main_keyboard(is_admin(call.from_user)))
        
    # Key Generator Callback (Admin Only)
    elif call.data == "menu_key_generator":
        bot.answer_callback_query(call.id)
        if not is_admin(call.from_user):
            edit_message_safe(chat_id, message_id, "❌ *Access Denied*", get_back_to_main_keyboard())
            return
        text = (
            "🔑 *𝗞𝗲𝘆 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗼𝗿 𝗠𝗲𝗻𝘂*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select the plan you want to deploy for the new key:"
        )
        edit_message_safe(chat_id, message_id, text, get_plan_selector_keyboard())
            
    # Profile Callback
    elif call.data == "menu_profile":
        bot.answer_callback_query(call.id)
        edit_message_safe(chat_id, message_id, "⏳ *Loading status...*")
        
        sender_id = str(call.from_user.id)
        sender_username = call.from_user.username or ""
        
        keys_ref = db.collection('access_keys')
        docs = keys_ref.where('telegramId', '==', sender_id).limit(1).get()
        if not docs and sender_username:
            docs = keys_ref.where('telegramId', '==', f"@{sender_username}").limit(1).get()
            if not docs:
                docs = keys_ref.where('telegramId', '==', sender_username).limit(1).get()
                
        if docs:
            existing_key = docs[0].id
            data = docs[0].to_dict()
            plan_name = escape_markdown(data.get('planName', 'Free Account'))
            status = escape_markdown(data.get('status', 'active')).upper()
            device_id = escape_markdown(data.get('deviceId', 'No device bound'))
            expires_at = escape_markdown(data.get('expiresAt', 'Lifetime'))
            
            try:
                if expires_at and expires_at != 'Lifetime':
                    dt = datetime.fromisoformat(expires_at.replace('Z', ''))
                    expires_at = dt.strftime('%Y-%m-%d')
            except:
                pass
                
            text = (
                f"👤 *𝗬𝗼𝘂𝗿 𝗦𝘁𝗮𝘁𝘂𝘀 / 𝗣𝗿𝗼𝗳𝗶𝗹𝗲* 👤\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"• *Telegram ID:* `{sender_id}`\n"
                f"• *Username:* `@{escape_markdown(sender_username) or 'None'}`\n"
                f"• *Access Code:* `{existing_key}`\n"
                f"• *Plan:* `{plan_name}`\n"
                f"• *Status:* `{status}`\n"
                f"• *Bound Device:* `{device_id}`\n"
                f"• *Expires:* `{expires_at}`"
            )
            edit_message_safe(chat_id, message_id, text, get_profile_keyboard(has_key=True, key_code=existing_key))
        else:
            text = (
                f"👤 *𝗬𝗼𝘂𝗿 𝗦𝘁𝗮𝘁𝘂𝘀 / 𝗣𝗿𝗼𝗳𝗶𝗹𝗲* 👤\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"• *Telegram ID:* `{sender_id}`\n"
                f"• *Username:* `@{escape_markdown(sender_username) or 'None'}`\n"
                f"• *Access Code:* `No key registered`\n\n"
                f"To get access, click the *✨ Generate Key* button in the Main Menu!"
            )
            edit_message_safe(chat_id, message_id, text, get_profile_keyboard(has_key=False))
            
    # App Download Callback (Sends APK directly in chat)
    elif call.data == "menu_download":
        bot.answer_callback_query(call.id, "📥 Sending app file...")
        edit_message_safe(chat_id, message_id, "⏳ *Preparing APK download...*")
        
        apk_filename = "naino-app.apk"
        apk_path = os.path.abspath(os.path.join(os.path.dirname(__file__), apk_filename))
        
        if os.path.exists(apk_path):
            try:
                with open(apk_path, 'rb') as f:
                    bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        visible_file_name="Naino_Academy.apk",
                        caption=(
                            "📥 *𝗡𝗮𝗶𝗻𝗼 𝗔𝗰𝗮𝗱𝗲𝗺𝘆 𝗔𝗽𝗽* 📥\n"
                            "━━━━━━━━━━━━━━━━━━━━━\n\n"
                            "Here is the latest version of the Naino Academy app for your Android device.\n\n"
                            "*Installation Steps:*\n"
                            "1. Download and open the APK file above.\n"
                            "2. Allow 'Install from Unknown Sources' in settings if prompted.\n"
                            "3. Open the app and log in using your Access Code!"
                        ),
                        parse_mode="Markdown"
                    )
                edit_message_safe(
                    chat_id, 
                    message_id, 
                    "✅ *App file sent successfully!*\n━━━━━━━━━━━━━━━━━━━━━\n\nCheck the document message sent below.",
                    get_back_to_main_keyboard()
                )
            except Exception as e:
                print(f"[Download] Failed to send APK document: {e}")
                # Fallback to link if send fails
                fallback_text = (
                    "📥 *𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 𝗡𝗮𝗶𝗻𝗼 𝗔𝗰𝗮𝗱𝗲𝗺𝘆 𝗔𝗽𝗽* 📥\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "Failed to send the file directly. You can download it here:\n\n"
                    "🚀 *[Download Direct APK](https://nainoacademy.com/download)*\n\n"
                    "*Installation Steps:*\n"
                    "1. Download the APK file from the link above.\n"
                    "2. Open the downloaded file and allow 'Install from Unknown Sources'.\n"
                    "3. Enter your Access Code to unlock study material!"
                )
                edit_message_safe(chat_id, message_id, fallback_text, get_back_to_main_keyboard())
        else:
            # Fallback if local file not found
            fallback_text = (
                "📥 *𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 𝗡𝗮𝗶𝗻𝗼 𝗔𝗰𝗮𝗱𝗲𝗺𝘆 𝗔𝗽𝗽* 📥\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "App file not found on the server. You can download it directly here:\n\n"
                "🚀 *[Download Direct APK](https://nainoacademy.com/download)*\n\n"
                "*Installation Steps:*\n"
                "1. Download the APK file from the link above.\n"
                "2. Open the downloaded file and allow 'Install from Unknown Sources'.\n"
                "3. Enter your Access Code to unlock study material!"
            )
            edit_message_safe(chat_id, message_id, fallback_text, get_back_to_main_keyboard())
        
    # Free Demo Key Callback (Now "Generate Key")
    elif call.data == "menu_free_key":
        bot.answer_callback_query(call.id)
        edit_message_safe(chat_id, message_id, "⏳ *Checking database...*")
        
        sender_id = str(call.from_user.id)
        sender_username = call.from_user.username or ""
        
        keys_ref = db.collection('access_keys')
        docs = keys_ref.where('telegramId', '==', sender_id).limit(1).get()
        if not docs and sender_username:
            docs = keys_ref.where('telegramId', '==', f"@{sender_username}").limit(1).get()
            if not docs:
                docs = keys_ref.where('telegramId', '==', sender_username).limit(1).get()
                
        if docs:
            existing_key = docs[0].id
            data = docs[0].to_dict()
            plan_name = escape_markdown(data.get('planName', 'Free Account'))
            text = (
                f"🔑 *𝗬𝗼𝘂𝗿 𝗔𝗰𝗰𝗲𝘀𝘀 𝗞𝗲𝘆*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"You already have an access key registered under your Telegram account:\n\n"
                f"• *Access Code:* `{existing_key}`\n"
                f"• *Plan:* `{plan_name}`\n\n"
                f"Tap the code above to copy it directly into Naino Academy app."
            )
            edit_message_safe(chat_id, message_id, text, get_back_to_main_keyboard())
        else:
            edit_message_safe(chat_id, message_id, "⏳ *Generating your Access Key...*")
            try:
                new_key = ""
                while True:
                    candidate = str(random.randint(100000, 999999))
                    if not keys_ref.document(candidate).get().exists:
                        new_key = candidate
                        break
                        
                now = datetime.utcnow()
                expires_at = now + timedelta(days=3652) # 10 years
                
                new_key_data = {
                    'planId': 'free',
                    'planName': 'Free Account',
                    'createdAt': now.isoformat() + 'Z',
                    'expiresAt': expires_at.isoformat() + 'Z',
                    'status': 'active',
                    'isPremium': False,
                    'telegramId': sender_id
                }
                
                keys_ref.document(new_key).set(new_key_data)
                
                text = (
                    f"🎉 *𝗔𝗰𝗰𝗲𝘀𝘀 𝗞𝗲𝘆 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱!* 🎉\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Here is your 6-digit access key registered to your Telegram account:\n\n"
                    f"• *Access Code:* `{new_key}`\n"
                    f"• *Plan:* `Free Account (10 Years)`\n\n"
                    f"Tap the code above to copy it directly into Naino Academy app."
                )
                edit_message_safe(chat_id, message_id, text, get_back_to_main_keyboard())
            except Exception as e:
                print(f"[Key Gen] Failed to generate key: {e}")
                edit_message_safe(chat_id, message_id, f"❌ *Error:* Failed to generate key: {e}", get_back_to_main_keyboard())
                
    # Support Callback
    elif call.data == "menu_support":
        bot.answer_callback_query(call.id)
        text = (
            "🆘 *𝗦𝘂𝗽𝗽𝗼𝗿𝘁 𝗖𝗼𝗻𝘁𝗮𝗰𝘁𝘀* 🆘\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "If you need help, feel free to contact us:\n\n"
            "• Click the buttons below to chat directly with our team."
        )
        edit_message_safe(chat_id, message_id, text, get_support_keyboard())
        
    # Reset Device Confirmation Callback
    elif call.data.startswith("reset_confirm_"):
        bot.answer_callback_query(call.id)
        key_code = call.data.replace("reset_confirm_", "")
        text = (
            f"⚠️ *𝗖𝗼𝗻𝗳𝗶𝗿𝗺 𝗗𝗲𝘃𝗶𝗰𝗲 𝗥𝗲𝘀𝗲𝘁* ⚠️\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Are you sure you want to reset the device binding for key `{key_code}`?\n\n"
            f"This will log out the active device immediately."
        )
        edit_message_safe(chat_id, message_id, text, get_reset_confirm_keyboard(key_code))
        
    # Reset Device Execution Callback
    elif call.data.startswith("reset_execute_"):
        bot.answer_callback_query(call.id, "⚡ Resetting...")
        key_code = call.data.replace("reset_execute_", "")
        edit_message_safe(chat_id, message_id, "⏳ *Resetting device binding...*")
        
        try:
            doc_ref = db.collection('access_keys').document(key_code)
            doc_snap = doc_ref.get()
            if not doc_snap.exists:
                edit_message_safe(chat_id, message_id, "❌ *Error:* Invalid Access Key.", get_back_to_main_keyboard())
                return
                
            data = doc_snap.to_dict()
            registered_telegram_id = str(data.get('telegramId', '')).strip()
            sender_id = str(call.from_user.id)
            sender_username = call.from_user.username or ""
            
            match_success = False
            clean_reg_tg = registered_telegram_id.lower().replace('@', '')
            clean_sender_uname = sender_username.lower().replace('@', '')
            
            if is_admin(call.from_user):
                match_success = True
            elif registered_telegram_id == sender_id:
                match_success = True
            elif clean_reg_tg and clean_reg_tg == clean_sender_uname:
                match_success = True
                
            if not match_success:
                edit_message_safe(chat_id, message_id, "❌ *Access Denied:* You cannot reset this key.", get_back_to_main_keyboard())
                return
                
            doc_ref.update({
                'deviceId': "",
                'pendingVerificationCode': None,
                'pendingDeviceId': None,
                'pendingVerificationCreatedAt': None
            })
            
            text = (
                "✅ *Reset Successful!*\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Your access key device binding has been completely cleared.\n"
                "You can now log in on any device."
            )
            edit_message_safe(chat_id, message_id, text, get_back_to_main_keyboard())
            print(f"{Colors.OKGREEN}[Result] Manual reset successful for key {key_code} via Inline callback.{Colors.ENDC}")
        except Exception as e:
            print(f"[Reset] Reset execution failed: {e}")
            edit_message_safe(chat_id, message_id, f"❌ *Error:* Reset failed: {e}", get_back_to_main_keyboard())
            
    # Plan Generator Callbacks (Admin only)
    elif call.data.startswith("gen_plan_"):
        if not is_admin(call.from_user):
            bot.answer_callback_query(call.id, "❌ Access Denied", show_alert=True)
            return
            
        plan_type = call.data.replace("gen_plan_", "")
        bot.answer_callback_query(call.id, "⚡ Deploying key...")
        edit_message_safe(chat_id, message_id, "⏳ *Deploying new key in Firestore...*")
        
        try:
            key, expires, plan_name = generate_new_key(plan_type)
            plan_name_esc = escape_markdown(plan_name)
            
            text = (
                f"🔑 *𝗞𝗲𝘆 𝗗𝗲𝗽𝗹𝗼𝘆𝗲𝗱 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆!* 🔑\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"• *Access Code:* `{key}`\n"
                f"• *Plan:* `{plan_name_esc}`\n"
                f"• *Expires:* `{expires}`\n\n"
                f"Tap the code above to copy it directly."
            )
            edit_message_safe(chat_id, message_id, text, get_back_to_main_keyboard())
            print(f"{Colors.OKGREEN}[Key Gen] Admin generated key {key} for {plan_name}{Colors.ENDC}")
        except Exception as e:
            print(f"[Key Gen] Generation failed: {e}")
            edit_message_safe(chat_id, message_id, f"❌ *Failed to generate key:* {e}", get_back_to_main_keyboard())


def log_user_to_channel(user):
    channel_id = os.environ.get('USER_LOG_CHANNEL_ID')
    if not channel_id:
        return
    try:
        username_str = f"@{user.username}" if user.username else "None"
        last_name_str = f" {user.last_name}" if user.last_name else ""
        full_name = f"{user.first_name}{last_name_str}"
        
        log_text = (
            "👤 *New Bot User Started!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Name:* `{escape_markdown(full_name)}`\n"
            f"• *Username:* {escape_markdown(username_str)}\n"
            f"• *User ID (Chat ID):* `{user.id}`\n"
            f"• *Profile Link:* [Click here to view](tg://user?id={user.id})\n"
        )
        bot.send_message(channel_id, log_text, parse_mode="Markdown")
    except Exception as e:
        print(f"[Log Channel] Failed to send user log to channel {channel_id}: {e}")


@bot.message_handler(commands=['ping'])
def handle_ping(message):
    bot.reply_to(message, "🏓 *Pong!* Bot is active and running.", parse_mode="Markdown")


# 3. Start Command Handler
@bot.message_handler(commands=['start'])
def handle_start(message):
    # Log user details to channel
    log_user_to_channel(message.from_user)
    
    # Block if membership check fails
    if not check_membership(message.from_user):
        send_membership_warning(message.chat.id)
        return
        
    args = message.text.split()
    if len(args) > 1:
        code = args[1]
        if code.isdigit() and len(code) == 4:
            verify_code(message, code)
            return
            
    # Clean up bottom keyboard if any
    try:
        cleanup = bot.send_message(message.chat.id, "⏳ *Initializing Naino Academy Bot...*", reply_markup=types.ReplyKeyboardRemove())
        bot.delete_message(message.chat.id, cleanup.message_id)
    except Exception as e:
        print(f"[Cleanup] Reply keyboard remover error: {e}")
        
    bot.send_message(
        message.chat.id,
        MAIN_MENU_TEXT,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(is_admin(message.from_user))
    )


# 4. Handle text and button actions
@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    text = message.text.strip()
    
    # Block if membership check fails
    if not check_membership(message.from_user):
        send_membership_warning(message.chat.id)
        return
        
    # Clean up bottom keyboard if they use any of the old text buttons
    if text in ["💎 Premium Plans", "👤 Profile", "📥 App Download", "📣 Feedback", "✨ Free Demo Key", "✨ Generate Key", "🆘 Support"]:
        try:
            cleanup = bot.send_message(message.chat.id, "🧹 *Updating menu...*", reply_markup=types.ReplyKeyboardRemove())
            bot.delete_message(message.chat.id, cleanup.message_id)
        except:
            pass
        bot.send_message(
            message.chat.id,
            MAIN_MENU_TEXT,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(is_admin(message.from_user))
        )
        return
        
    # Handle numeric input codes (4-digit verification or 6-digit key reset)
    if text.isdigit():
        if len(text) == 4:
            verify_code(message, text)
        elif len(text) == 6:
            reset_key_manually(message, text)
        else:
            bot.reply_to(
                message,
                "⚠️ *𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗻𝘂𝗺𝗲𝗿𝗶𝗰 𝗰𝗼𝗱𝗲 𝗹𝗲𝗻𝗴𝘁𝗵.*\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "- Send a *4-digit code* to authorize a new device.\n"
                "- Send your *6-digit Access Key* to clear its device binding.",
                parse_mode="Markdown"
            )
            
    else:
        bot.reply_to(
            message,
            "ℹ️ *𝗨𝗻𝗸𝗻𝗼𝘄𝗻 𝗜𝗻𝗽𝘂𝘁.*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "To use the menu, please click the inline buttons above.\n"
            "Or send a valid verification/access code.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(is_admin(message.from_user))
        )


def run_health_check_server():
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import os

    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, format, *args):
            # Suppress logs to keep terminal clean
            pass

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"[Health Check] Server listening on port {port}...")
    server.serve_forever()


if __name__ == '__main__':
    import threading
    import time
    
    # Start the HTTP health check server in a background daemon thread
    health_thread = threading.Thread(target=run_health_check_server, daemon=True)
    health_thread.start()

    print(f"\n{Colors.OKGREEN}Bot is now polling and waiting for messages...{Colors.ENDC}")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"{Colors.FAIL}Bot polling crashed: {e}. Restarting in 5 seconds...{Colors.ENDC}")
            time.sleep(5)
