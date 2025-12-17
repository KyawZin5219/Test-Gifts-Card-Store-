import logging
import os
from motor.motor_asyncio import AsyncIOMotorClient 
import asyncio
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton,BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, PrefixHandler

# --- CONFIGURATION ---
# Code ထဲမှာ တိုက်ရိုက်မရေးဘဲ Render Setting ထဲကနေ လှမ်းယူမယ်
TOKEN = os.getenv('BOT_TOKEN') 
MONGO_URI = os.getenv('MONGO_URI') 
ADMIN_ID = int(os.getenv('ADMIN_ID', '1953106131')) # Default ID ထည့်ထားလို့ရပါတယ်

MONGO_DB_NAME = "giftcard_bot"


# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- MONGODB CONNECTION & VARIABLES ---
try:
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['GameShopDB']
    # Collections
    users_col = db['users']
    stocks_col = db['stocks']
    orders_col = db['orders']
    history_col = db['history']
    promos_col = db['promos']
except Exception as e:
    print(f"DB Connection Error: {e}")

# Global Variables (Empty Dictionary အဖြစ်ထားမယ်)
USER_DB = {}
STOCKS = {}
PENDING_ORDERS = {}
HISTORY_DB = {}
PROMO_DB = {}

# Status Variables
IS_ADMIN_ONLINE = True 
IS_SHOP_OPEN = True  # New: ဆိုင်ဖွင့်/ပိတ် စနစ်

#အသစ်ထည့် Mango
# --- DATABASE HELPER FUNCTIONS ---

async def load_data_from_mongo():
    global USER_DB, STOCKS, PENDING_ORDERS, HISTORY_DB, PROMO_DB
    print("🔄 Loading Data...")
    try:
        async for doc in users_col.find(): USER_DB[str(doc['_id'])] = doc
        async for doc in stocks_col.find(): STOCKS[doc['_id']] = doc['codes']
        async for doc in orders_col.find(): PENDING_ORDERS[int(doc['_id'])] = doc['data']
        async for doc in history_col.find(): HISTORY_DB[str(doc['_id'])] = doc['records']
        async for doc in promos_col.find(): PROMO_DB[doc['_id']] = doc['data']
        print("✅ Data Loaded!")
    except Exception as e: print(f"❌ Load Error: {e}")

async def update_user_db(user_id):
    str_id = str(user_id)
    if str_id in USER_DB:
        data = USER_DB[str_id].copy()
        if '_id' in data: del data['_id']
        await users_col.update_one({'_id': str_id}, {'$set': data}, upsert=True)

async def update_stock_db(key):
    if key in STOCKS:
        await stocks_col.update_one({'_id': key}, {'$set': {'codes': STOCKS[key]}}, upsert=True)
        
        # ဒီ Function လေး မရှိလို့ Error တက်နေတာပါ (ကူးထည့်လိုက်ပါ)
async def update_promo_db():
    if 'PROMO_CODES' in globals():
        await promos_col.update_one(
            {'_id': 'promo_list'}, 
            {'$set': {'codes': PROMO_CODES}}, 
            upsert=True
        )


async def update_order_db(user_id):
    if user_id in PENDING_ORDERS:
        await orders_col.update_one({'_id': user_id}, {'$set': {'data': PENDING_ORDERS[user_id]}}, upsert=True)

async def delete_order_db(user_id):
    await orders_col.delete_one({'_id': user_id})

async def update_history_db(user_id):
    str_id = str(user_id)
    if str_id in HISTORY_DB:
        await history_col.update_one({'_id': str_id}, {'$set': {'records': HISTORY_DB[str_id]}}, upsert=True)


def get_user(user_id):
    """User Data ကိုဆွဲထုတ်ခြင်း (မရှိလျှင် အသစ်ဆောက်သည်)"""
    str_id = str(user_id)
    if str_id not in USER_DB:
        USER_DB[str_id] = {"points": 0, "invited_by": None, "referrals": 0, "banned": False}
          
   #အသစ်mango
    return USER_DB[str_id]

# --- ဈေးနှုန်း DATA များ ---
PRICES = {
    # --- STEAM ---
    "steam.us": {
        "text": "Steam Wallet (🇺🇸 US)",
        "items": {"$5": "23,000 Ks", "$10": "45,000 Ks", "$20": "88,000 Ks", "$30": "129,000 Ks"}
    },
    "steam.sg": {
        "text": "Steam Wallet (🇸🇬 SG)",
        "items": {"$5 SGD": "15,800 Ks", "$10 SGD": "31,600 Ks", "$15 SGD": "47,400 Ks", "$20 SGD": "63,000 Ks", "$30 SGD": "94,500 Ks", "$40 SGD": "126,000 Ks", "$50 SGD": "157,000 Ks"}
    },
    "steam.in": {
        "text": "Steam Wallet (🇮🇳 India)",
        "items": {"₹99": "7500 Ks", "₹250": "17,000 Ks", "₹500": "33,00 Ks", "₹650": "41,000 Ks", "₹860": "53,500 Ks", "₹1000": "65,000 Ks", "₹1720": "105,700 Ks"}       
    },
    "steam.th": {
        "text": "Steam Wallet (🇹🇭 Thai)",
        "items": {"฿350": "0 Ks", "฿500": "0 Ks", "฿1000": "0 Ks"}
    },
    "steam.ar": {
        "text": "Steam Wallet (🇦🇷 Argentina)",
        "items": {"1000 ARS": "0 Ks", "2000 ARS": "0 Ks"}
    },
    "steam.tr": {
        "text": "Steam Wallet (🇹🇷 Turkey)",
        "items": {"100 TL": ",000 Ks", "200 TL": "0 Ks"}
    },
    "steam.cn": {
        "text": "Steam Wallet (🇨🇳 China)",
        "items": {"¥30": "0 Ks", "¥100": "0 Ks", "¥300": "0 Ks"}
    },
    
    # --- APPLE ---
    "apple.us": {
        "text": "Apple Gift Card (🇺🇸 US)",
        "items": {"$2": " Ks", "$5": "20,400 Ks", "$10": "40,700 Ks", "$20": "81,200 Ks", "$50": "203,000 Ks" }
    },
    "apple.sg": {
        "text": "Apple Gift Card (🇸🇬 SG)",
        "items": {"$10 SGD": "0 Ks", "$20 SGD": "0 Ks"}
    },
    "apple.tr": {
        "text": "Apple Gift Card (🇹🇷 Turkey)",
        "items": {"25 TL": "3,500Ks", "50 TL": "6,000 Ks","100 TL": "11,000Ks","250 TL": "27,500Ks","500 TL": "55,000Ks","1000 TL": "110,000Ks"}
    },

    # --- PLAYSTATION ---
    "psn.us": {
        "text": "PSN Gift Card (🇺🇸 US)",
        "items": {"$10": "39,700 Ks", "$20": "79,000 Ks", "$25": "99,500 Ks", "$50": "199,000 Ks"}
    },
    "psn.sg": {
        "text": "PSN Gift Card (🇸🇬 SG)",
        "items": {"$15 SGD": "47,800 Ks", "$20 SGD": "62,900 Ks", "$30 SGD": "94,500 Ks", "$40 SGD": "125,500 Ks", "$50 SGD": "156,900 Ks"}
    },

    # --- NINTENDO ---
    "nintendo.us": {
        "text": "Nintendo eShop (🇺🇸 US)",
        "items": {"$5": "21,000 Ks", "$10": "45,000 Ks", "$20": "80,500 Ks", "$35": "141,800", "$50": "195,900 Ks"}
    },
    "nintendo.jp": {
        "text": "Nintendo eShop (🇯🇵 Japan)",
        "items": {"¥1000": "0 Ks", "¥3000": "0 Ks"}
    },
    "nintendo.sg": {
        "text": "Nintendo eShop (🇸🇬 SG)",
        "items": {"$20 SGD": "0 Ks", "$50 SGD": "0 Ks"}
    },
    "nintendo.uk": {
        "text": "Nintendo eShop (🇬🇧 UK)",
        "items": {"£15": "0 Ks", "£25": "0 Ks"}
    },

    # --- ROBLOX ---
    "roblox.us": {
        "text": "Roblox Gift Card (🇺🇸 US)",
        "items": {"$10": "42,000 Ks", "$20": "81,500 Ks", "$25": "0 Ks", "$50": "0 Ks"}
    },
    # --- VISA & MASTERCARD ---
    "visa.us": {
        "text": "Visa Gift Card (🇺🇸 US)",
        "items": {"$5": "0 Ks", "$10": "0 Ks", "$25": "0 Ks", "$50": "0 Ks"}
    },
    "mastercard.us": {
        "text": "Mastercard (🇺🇸 US)",
        "items": {"$1": "9,300 Ks", "$2": "13,400 Ks", "$3": "17,300 Ks", "$5": "27,500 Ks"}
    },
    "tg.prem": {
        "text": "🌟 Telegram Premium",
        "items": {"3 Month": "58,000 Ks", "6 Months": "77,000 Ks", "1 Year": "0 Ks"}
    },
}

# --- BACKGROUND TASKS (Auto Backup) ---
# --- AUTO BACKUP JOB (JobQueue စနစ်သုံးမည်) ---
async def auto_backup_job(context: ContextTypes.DEFAULT_TYPE):
    # Admin ID ကို စစ်မယ်
    chat_id = ADMIN_ID 
    
    # ပို့ရမည့် ဖိုင်စာရင်း
    files = [DB_FILE, STOCK_FILE, ORDER_FILE, HISTORY_FILE, PROMO_FILE]
    
    # Admin ဆီ စာပို့မယ်
    try:
        await context.bot.send_message(chat_id=chat_id, text="📦 **Auto Backup:** System files are being uploaded...", parse_mode='Markdown')
        
        for file_name in files:
            if os.path.exists(file_name):
                try:
                    await context.bot.send_document(
                        chat_id=chat_id, 
                        document=open(file_name, 'rb'), 
                        caption=f"📂 Backup: `{file_name}`",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"Backup Error ({file_name}): {e}")
    except Exception as e:
        print(f"Backup Job Failed: {e}")

            
# --- MANUAL BACKUP COMMAND ---
       
async def force_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin ဟုတ်မဟုတ် စစ်မည်
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text("📦 **Backup Process Started...**\nData ဖိုင်များကို စတင်ပို့ဆောင်ပေးနေပါပြီ...", parse_mode='Markdown')
    
    # ပို့ရမည့် ဖိုင်စာရင်း
    files = [DB_FILE, STOCK_FILE, ORDER_FILE, HISTORY_FILE, PROMO_FILE]
    
    found_files = 0
    for file_name in files:
        if os.path.exists(file_name):
            try:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id, 
                    document=open(file_name, 'rb'), 
                    caption=f"📂 **Backup:** `{file_name}`",
                    parse_mode='Markdown'
                )
                found_files += 1
            except Exception as e:
                await update.message.reply_text(f"❌ Error sending {file_name}: {e}")
        else:
            # ဖိုင်မရှိသေးရင် (ဥပမာ Promo မလုပ်ရသေးရင် Promo file ရှိမှာမဟုတ်ဘူး)
            pass 

    if found_files == 0:
        await update.message.reply_text("⚠️ **No Data Found!**\nပို့စရာ Data ဖိုင်တစ်ခုမှ မရှိသေးပါ။")
    else:
        await update.message.reply_text(f"✅ **Backup Completed!**\nစုစုပေါင်း ဖိုင် ({found_files}) ခု ပို့ပြီးပါပြီ။", parse_mode='Markdown')


# --- NEW FEATURES: PROMO & MAINTENANCE ---

# 1. Maintenance Mode
async def open_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    global IS_SHOP_OPEN
    IS_SHOP_OPEN = True
    await update.message.reply_text("✅ **Shop Opened!**\nဆိုင်ပြန်ဖွင့်လိုက်ပါပြီ။ User များ ပုံမှန်အတိုင်း ဝယ်ယူနိုင်ပါပြီ။", parse_mode='Markdown')

async def close_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    global IS_SHOP_OPEN
    IS_SHOP_OPEN = False
    await update.message.reply_text("⛔ **Shop Closed!**\nဆိုင်ခေတ္တပိတ်လိုက်ပါပြီ။", parse_mode='Markdown')

# 2. Promo Code System

async def add_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        # Command: /addpromo CODE POINTS [TIME] [LIMIT]
        # အချိန်နဲ့ လူအရေအတွက်က ကြိုက်တာ အရင်လာလို့ရပါတယ်
        
        args = context.args
        if len(args) < 2:
            raise IndexError

        code = args[0].upper()
        points = int(args[1])
        
        expire_time = None
        user_limit = None # None ဆိုရင် အကန့်အသတ်မရှိ
        
        duration_str = "Forever (သက်တမ်းမရှိ)"
        limit_str = "Unlimited (လူအကန့်အသတ်မရှိ)"

        # Argument 3 နဲ့ 4 ကို လိုက်စစ်မယ် (အချိန်လား လူရေအတွက်လား)
        for arg in args[2:]:
            arg = arg.lower()
            
            # ဂဏန်းသက်သက်ဆိုရင် လူအရေအတွက် (Limit) လို့သတ်မှတ်မယ်
            if arg.isdigit():
                user_limit = int(arg)
                limit_str = f"{user_limit} Users"
            
            # m, h, d နဲ့ဆုံးရင် အချိန် (Duration) လို့သတ်မှတ်မယ်
            elif arg.endswith("m") or arg.endswith("h") or arg.endswith("d"):
                duration_str = arg
                now = datetime.now()
                if arg.endswith("m"):
                    expire_time = now + timedelta(minutes=int(arg.replace("m", "")))
                elif arg.endswith("h"):
                    expire_time = now + timedelta(hours=int(arg.replace("h", "")))
                elif arg.endswith("d"):
                    expire_time = now + timedelta(days=int(arg.replace("d", "")))

        # Database ထဲသိမ်းခြင်း
        promo_data = {
            "points": points, 
            "used_by": []
        }
        
        if expire_time:
            promo_data["expire_at"] = expire_time.strftime("%Y-%m-%d %H:%M:%S")
        
        if user_limit:
            promo_data["max_users"] = user_limit # လူအရေအတွက် သိမ်းမယ်

        PROMO_DB[code] = promo_data
        await update_promo_db(code)
        #အသစ်ထည့် Mango
        
        readable_time = expire_time.strftime("%Y-%m-%d %I:%M %p") if expire_time else "Never"
        
        await update.message.reply_text(
            f"🎟️ **Promo Code Created!**\n\n"
            f"Code: `{code}`\n"
            f"Points: `{points}`\n"
            f"Duration: `{duration_str}`\n"
            f"Limit: `{limit_str}`\n"
            f"Expires On: `{readable_time}`", 
            parse_mode='Markdown'
        )

    except IndexError:
        await update.message.reply_text(
            "အသုံးပြုပုံ:\n"
            "၁။ ရိုးရိုး: `/addpromo <CODE> <POINTS>`\n"
            "၂။ လူကန့်သတ်: `/addpromo <CODE> <POINTS> <LIMIT>`\n"
            "၃။ အချိန်ကန့်သတ်: `/addpromo <CODE> <POINTS> <TIME>`\n"
            "၄။ နှစ်မျိုးလုံး: `/addpromo <CODE> <POINTS> <TIME> <LIMIT>`",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Points ပမာဏ မှားယွင်းနေပါသည်။")

async def redeem_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    try:
        code = context.args[0].upper()
        if code in PROMO_DB:
            promo_data = PROMO_DB[code]
            
            # ၁. သုံးပြီးသားလား စစ်မယ်
            if user_id in promo_data["used_by"]:
                await update.message.reply_text("⚠️ ဒီကူပွန်ကုဒ်ကို လူကြီးမင်း အသုံးပြုပြီးပါပြီ။")
                return
            
            # ၂. သက်တမ်းကုန်ပြီလား စစ်မယ်
            if "expire_at" in promo_data:
                expire_str = promo_data["expire_at"]
                expire_dt = datetime.strptime(expire_str, "%Y-%m-%d %H:%M:%S")
                if datetime.now() > expire_dt:
                    await update.message.reply_text(f"❌ **Expired!**\nဒီ Code ၏ သက်တမ်း ({expire_str}) ကုန်ဆုံးသွားပါပြီ။")
                    return

            # ၃. လူဦးရေ ပြည့်ပြီလား စစ်မယ် (New Feature)
            if "max_users" in promo_data:
                limit = promo_data["max_users"]
                current_used = len(promo_data["used_by"])
                if current_used >= limit:
                    await update.message.reply_text(f"❌ **Limit Reached!**\nဒီ Code ကို လူ ({limit}) ယောက် အသုံးပြုသွားပါပြီ။ ထပ်မံအသုံးပြု၍ မရတော့ပါ။")
                    return

            # အကုန်မှန်ရင် Points ပေးမယ်
            points = promo_data["points"]
            get_user(user_id) 
            USER_DB[user_id]["points"] += points
            
            # Mark as used
            PROMO_DB[code]["used_by"].append(user_id)
            await update_promo_db(code)
            await update_user_db(user_id)
            #အသစနှစ်ခုထည့် mango
            
            await update.message.reply_text(f"🎉 **ဂုဏ်ယူပါတယ်။**\nကူပွန်အသုံးပြုမှု အောင်မြင်ပါသည်။ **{points} Points** ရရှိပါသည်။", parse_mode='Markdown')
            
            # NOTIFY OWNER
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 **Promo Used!**\nUser: {update.effective_user.first_name}\nCode: `{code}`\nPoints Given: {points}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ မှားယွင်းသော ကုဒ်ဖြစ်ပါသည်။")
    except IndexError:
        await update.message.reply_text("အသုံးပြုပုံ: `/redeem <code>`", parse_mode='Markdown')


# 3. Purchase History
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in HISTORY_DB and len(HISTORY_DB[user_id]) > 0:
        msg = "📜 **မိမိဝယ်ယူခဲ့သော မှတ်တမ်းများ**\n\n"
        # Show last 10 orders
        for order in reversed(HISTORY_DB[user_id][-10:]):
            msg += f"📅 {order['date']}\n🛒 {order['item']}\n🔑 `{order['code']}`\n➖➖➖➖➖➖\n"
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        await update.message.reply_text("📭 ဝယ်ယူမှုမှတ်တမ်း မရှိသေးပါ။")

async def save_to_history(user_id, item_name, code):
    str_id = str(user_id)
    if str_id not in HISTORY_DB:
        HISTORY_DB[str_id] = []
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    HISTORY_DB[str_id].append({
        "date": timestamp,
        "item": item_name,
        "code": code
    })
    # str_id ဆိုတာ အပေါ်နားမှာ ကြေညာထားတဲ့ User ID (String) ပါ
    await update_history_db(str_id)


# ⚠️⚠️--- ADMIN DASHBOARD ---

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    # User ရိုက်လိုက်တဲ့ စာကို ယူမယ် (ဥပမာ: .stats သို့မဟုတ် /stats)
    full_text = update.message.text.split()
    command = full_text[0] 

    # 1. Check Total Users (stats ပါရင် အလုပ်လုပ်မယ်)
    if "stats" in command:
        total_users = len(USER_DB)
        total_stock = sum(len(codes) for codes in STOCKS.values())
        msg = (
            f"📊 **Bot Statistics**\n\n"
            f"👥 Total Users: `{total_users}`\n"
            f"📦 Available Stock Codes: `{total_stock}`\n"
            f"🏪 Shop Status: `{'ဖွင့်ထားသည် ✅' if IS_SHOP_OPEN else 'ပိတ်ထားသည် ⛔'}`\n"
            f"📂 Database File: `{DB_FILE}`"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    # 2. Broadcast Message (cast ပါရင် အလုပ်လုပ်မယ်)
    elif "cast" in command:
        msg_to_send = " ".join(context.args)
        if not msg_to_send:
            await update.message.reply_text("အသုံးပြုပုံ: `.cast ဒီမှာ စာရိုက်ပါ`", parse_mode='Markdown')
            return

        status_msg = await update.message.reply_text(f"🚀 User {len(USER_DB)} ယောက်ကို စာစပို့နေပါပြီ...")
        
        success_count = 0
        block_count = 0
        
        for user_id in USER_DB:
            try:
                await context.bot.send_message(chat_id=int(user_id), text=f"📢 **Admin Announcement**\n\n{msg_to_send}", parse_mode='Markdown')
                success_count += 1
            except Exception:
                block_count += 1
        
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, 
                                            text=f"✅ ပို့ပြီးပါပြီ။\nအောင်မြင်: {success_count}\nမအောင်မြင် (Block): {block_count}")

    # 3. Direct Message (msg ပါရင် အလုပ်လုပ်မယ်)
    elif "msg" in command:
        if len(context.args) < 2:
            await update.message.reply_text("အသုံးပြုပုံ: `.msg <user_id> <message>`", parse_mode='Markdown')
            return
            
        target_id = context.args[0]
        msg_text = " ".join(context.args[1:])
        
        try:
            await context.bot.send_message(chat_id=int(target_id), text=f"📩 **Message from Admin**\n\n{msg_text}", parse_mode='Markdown')
            await update.message.reply_text(f"✅ User ID `{target_id}` သို့ စာပို့ပြီးပါပြီ။", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ မအောင်မြင်ပါ။ Error: {e}")

            
            # --- BAN SYSTEM ---
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = context.args[0]
        if target_id not in USER_DB: USER_DB[target_id] = {"points": 0, "invited_by": None, "referrals": 0}
        USER_DB[target_id]["banned"] = True
       # target_id ဆိုတာ Ban ခံရတဲ့သူရဲ့ ID ပါ
        await update_user_db(target_id)
        await update.message.reply_text(f"🚫 User `{target_id}` ကို Ban လိုက်ပါပြီ။", parse_mode='Markdown')
    except IndexError: await update.message.reply_text("Usage: `/ban <user_id>`")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = context.args[0]
        if target_id in USER_DB:
            USER_DB[target_id]["banned"] = False
            # target_id ဆိုတာ Ban ခံရတဲ့သူရဲ့ ID ပါ
            await update_user_db(target_id)
            await update.message.reply_text(f"✅ User `{target_id}` ကို Ban ပြန်ဖြုတ်လိုက်ပါပြီ။", parse_mode='Markdown')
    except IndexError: await update.message.reply_text("Usage: `/unban <user_id>`")
        
# --- KEYBOARDS & MENUS ---

async def show_persistent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🛍️ ဈေးဝယ်ရန်"), KeyboardButton("🎁 ပရိုမိုးရှင်း")],
        [KeyboardButton("👤 မိမိအကောင့်"), KeyboardButton("📜 မှတ်တမ်း")],
        [KeyboardButton("📞 ဆက်သွယ်ရန်"), KeyboardButton("🤝 သူငယ်ချင်းဖိတ်ရန်")]
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    text = "🏠 **Chikii Gift Card Shop မှ လူကြီးမင်း လိုအပ်သော Gift Card များကို ယုံကြည်စွာ ဝယ်ယူနိုင်ပါတယ် **\n\n   Sell Proof များ ကြည့်ရှု န်ိုင်ပါတယ်ဗျ                 https://t.me/ChikiiandKYDigitalProof                              အသုံးပြုနည်း ကြည့်ရန်                                       https://t.me/AllinonestoreMm                            /Redeem 500 လို့ Bot ဆီကို စာပို့ပြီး Points 500 လက်ဆောင်ရယူပါ။"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode='Markdown')

async def show_shop_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check Maintenance Mode (Admin ကလွဲရင် ကျန်လူတွေ ဝင်မရအောင် ပိတ်မယ်)
    if not IS_SHOP_OPEN and update.effective_user.id != ADMIN_ID:
        if update.message: await update.message.reply_text("⛔ **ဒီနေ့အတွက် ဆိုင်ပိတ်ပါပြီခင်ဗျ **\n\nဆိုင်ဖွင့်ချိန် > မနက် 9နာရီ to ည 10နာရီ    ကျေးဇူးတင်ပါတယ်😘                                    DMမှာတော့  Admin မအိပ်မချင်းတော့ ရပါတယ်ဗျ။", parse_mode='Markdown')
        elif update.callback_query: await update.callback_query.answer("ဆိုင်ခေတ္တပိတ်ထားပါသည်", show_alert=True)
        return

    keyboard = [
        [InlineKeyboardButton("Steam Wallet", callback_data='steam_main')], 
        [InlineKeyboardButton("Apple Gift Card", callback_data='apple_main')],
        [InlineKeyboardButton("PSN Gift Card", callback_data='psn_main')],
        [InlineKeyboardButton("Nintendo eShop", callback_data='nintendo_main')],
        [InlineKeyboardButton("Roblox Gift Card", callback_data='roblox_main')],
         [InlineKeyboardButton("🌟 Telegram Premium", callback_data='tg_prem_main')],
         [InlineKeyboardButton("Visa GiftCard",callback_data='visa_main')],
         [InlineKeyboardButton("Mastercard", callback_data='mastercard_main')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "မိမိဝယ်ယူလိုသော Gift Card အမျိုးအစားကို ရွေးချယ်ပါ -"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

# --- CORE HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (၁) Ban ထားလား စစ်မယ်
    user_data = get_user(update.effective_user.id)
    if user_data.get("banned", False):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ **Access Denied**", parse_mode='Markdown')
        return

    user_id = str(update.effective_user.id)
    
    # (၂) User အသစ်လား စစ်မယ်
    if user_id not in USER_DB:
        # User အသစ်မို့ Default Data တွေ အရင်ထည့်မယ်
        USER_DB[user_id] = {"points": 0, "invited_by": None, "referrals": 0, "banned": False}
        
        # (၃) Referral ကုဒ် ပါ/မပါ စစ်မယ်
        args = context.args
        if args and args[0] != user_id: 
            referrer_id = args[0]
            
            # Referrer ID က Database ထဲမှာ တကယ်ရှိလား စစ်မယ်
            if referrer_id in USER_DB:
                USER_DB[user_id]["invited_by"] = referrer_id
                USER_DB[referrer_id]["referrals"] += 1 
                
                # ✅ (၄) မိတ်ဆက်ပေးသူ (Referrer) ကို ဒီနားမှာတင် ချက်ချင်း Save ပါ
                await update_user_db(referrer_id)

    # ✅ (၅) User (ကိုယ့်အကောင့်) ကို Save မယ် 
    # (User အသစ်ပဲဖြစ်ဖြစ်၊ အဟောင်းပဲဖြစ်ဖြစ် ဒီနားရောက်ရင် Save လိုက်တာ စိတ်ချရပါတယ်)
    await update_user_db(user_id)
    
    # ✅ (၆) Menu ပြမယ်
    await show_persistent_menu(update, context)


# --- MENU COMMAND HANDLERS ---
async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_shop_categories(update, context)

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📞 **Contact Support**\n\nAdmin: @KyawZiinn\nTime: 9:00 AM - 9:00 PM"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user(update.effective_user.id)
    points = user_data.get('points', 0)
    refs = user_data.get('referrals', 0)
    msg = (
        f"👤 **User Information**\n\n"
        f"Name: {update.effective_user.first_name}\n"
        f"ID: `{update.effective_user.id}`\n"
        f"💰 **My Points:** {points}\n"
        f"👥 **Invited:** {refs} friends"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- BOT STARTUP MENU SETUP ---
async def post_init(application):
    # ဒီနေရာမှာ Menu စာရင်းကို သတ်မှတ်ပါတယ်
    commands = [
        BotCommand("start", "ပင်မစာမျက်နှာ"),
        BotCommand("shop", "ဈေးဝယ်ရန်"),
        BotCommand("account", "မိမိအကောင့်"),
        BotCommand("myorders", "ဝယ်ယူမှုမှတ်တမ်း"),
        BotCommand("contact", "ဆက်သွယ်ရန်"),
        BotCommand("redeem", "ကူပွန်အသုံးပြုရန်")
    ]
    await application.bot.set_my_commands(commands)


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user(update.effective_user.id)
    if user_data.get("banned", False):
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="⛔ **Access Denied**\n\nလူကြီးမင်း၏ အကောင့်အား Ban ထားပါသဖြင့် ဤ Bot ကို ဆက်လက်အသုံးပြု၍ မရနိုင်တော့ပါ။", 
            parse_mode='Markdown'
        )
        return

    text = update.message.text
    user = update.message.from_user

    if text == "🛍️ ဈေးဝယ်ရန်":
        await show_shop_categories(update, context)
        
    elif text == "🤝 သူငယ်ချင်းဖိတ်ရန်":
        bot_username = context.bot.username
        invite_link = f"https://t.me/{bot_username}?start={user.id}"
        msg = (
            "🤝 **Invite Friends & Earn Points**\n\n"
            "သူငယ်ချင်းများကို ဖိတ်ခေါ်ပြီး လက်ဆောင်များ ရယူလိုက်ပါ။\n"
            "⚠️ **Note:** သူငယ်ချင်းက ပစ္စည်းတစ်ခုခုကို ဝယ်ယူအောင်မြင်မှသာ Point (100) ရရှိပါမည်။\n\n"
            f"🔗 **Your Invite Link:**\n`{invite_link}`\n\n"
            "👆 Link ကိုနှိပ်ပြီး Copy ကူး၍ သူငယ်ချင်းများကို ပို့ပေးပါ။"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    elif text == "🎁 ပရိုမိုးရှင်း":
        await update.message.reply_text("ကူပွန်အသုံးပြုရန်:\n`/redeem <code>` ဟု ရိုက်ထည့်ပါ။", parse_mode='Markdown')
        
    elif text == "👤 မိမိအကောင့်":
        points = user_data.get('points', 0)
        refs = user_data.get('referrals', 0)
        msg = (
            f"👤 **User Information**\n\n"
            f"Name: {user.first_name}\n"
            f"ID: `{user.id}`\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"💰 **My Points:** {points}\n"
            f"👥 **Invited:** {refs} friends\n"
            f"➖➖➖➖➖➖➖➖"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    elif text == "📜 မှတ်တမ်း":
        await my_orders(update, context)

    elif text == "📞 ဆက်သွယ်ရန်":
        msg = (
            "📞 **Contact Support**\n\n"
            "အကူအညီလိုပါက Admin သို့ တိုက်ရိုက်ဆက်သွယ်နိုင်ပါသည်။\n"
            "👤 Admin: @KyawZiinn\n"
            "⏰ Time: 9:00 AM - 9:00 PM"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
    elif text == "ℹ️ သတင်းအချက်အလက်":
        msg = (
            "ℹ️ **Information**\n\n"
            " Chikii Gift Card Shop မှ ကြိုဆိုပါတယ်။\n"
            "ကျွန်တော်တို့ဆီမှာ Steam, Apple, PSN Gift Card များကို ယုံကြည်စိတ်ချစွာ ဝယ်ယူနိုင်ပါသည်။"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user(update.effective_user.id)
    if user_data.get("banned", False):
        if update.callback_query: await update.callback_query.answer()
        return

    query = update.callback_query
    try: await query.answer()
    except: pass
    
    data = query.data

    # --- ADMIN ACTIONS ---
    if data.startswith('admin|'):
        if update.callback_query.from_user.id != ADMIN_ID: return 
        try:
            parts = data.split('|')
            action = parts[1]
            user_id_int = int(parts[2]) 
            user_id_str = str(user_id_int) 
            
            if action == "accept":
                global IS_ADMIN_ONLINE
                if not IS_ADMIN_ONLINE:
                    await query.answer("⚠️ Admin Offline ဖြစ်နေပါသည်!\n\n/online နှိပ်ပြီး ဖွင့်ပါ", show_alert=True)
                    return 

                order_details = PENDING_ORDERS.get(user_id_int)
                used_points = 0
                
                if order_details and 'final_point_deduct' in order_details:
                    used_points = order_details['final_point_deduct']
                    if used_points > 0:
                        if user_id_str in USER_DB:
                            if USER_DB[user_id_str]["points"] >= used_points:
                                USER_DB[user_id_str]["points"] -= used_points
                                try: await update_user_db(user_id_str)
                                except: pass
                                
                                try: await context.bot.send_message(chat_id=user_id_int, text=f"💎 **Points Used!**\nOrdered items: -{used_points} Points", parse_mode='Markdown')
                                except: pass

                await context.bot.send_message(chat_id=user_id_int, text="✅ **Payment Verified!**\n\nAdmin မှ ငွေလွှဲစစ်ဆေးပြီးပါပြီ။ Code ပို့ပေးပါမည်။", parse_mode='Markdown')

                stock_count = 0
                item_full_name = "Unknown" 
                if order_details:
                    item_full_name = f"{order_details['product_name']} {order_details['amt']}"
                    cat = order_details['cat']
                    amt = order_details['amt']
                    stock_key = f"{cat}|{amt}"
                    if stock_key in STOCKS: stock_count = len(STOCKS[stock_key])
                
                confirm_text = (
                    f"✅ **Payment Accepted** for User `{user_id_int}`\n"
                    f"🛒 Order: **{item_full_name}**\n"
                    f"💎 Points Used: **{used_points}**\n"
                    f"📦 Stock: **{stock_count}** codes\n\n"
                    "Choose Action:"
                )
                confirm_keyboard = [
                    [InlineKeyboardButton(f"🚀 Auto ({stock_count})", callback_data=f"admin|autosend|{user_id_int}")],
                    [InlineKeyboardButton("✍️ Manual Send", callback_data=f"admin|manual|{user_id_int}")]
                ]
                await query.edit_message_caption(caption=confirm_text, reply_markup=InlineKeyboardMarkup(confirm_keyboard), parse_mode='Markdown')

            elif action == "autosend":
                order_details = PENDING_ORDERS.get(user_id_int)
                if not order_details:
                    await query.answer("Order expired!", show_alert=True)
                    return
                stock_key = f"{order_details['cat']}|{order_details['amt']}"
                if stock_key in STOCKS and len(STOCKS[stock_key]) > 0:
                    code_to_send = STOCKS[stock_key].pop(0)
                    try: await update_stock_db(stock_key)
                    except: pass
                    
                    full_item_name = f"{order_details['product_name']} {order_details['amt']}"
                    await process_successful_order(update, context, user_id_int, code_to_send, full_item_name)
                    
                    if len(STOCKS[stock_key]) < 2:
                         try: await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ **Low Stock:** {stock_key}")
                         except: pass

                    await query.edit_message_caption(caption=f"✅ **Auto Sent!**\nCode: `{code_to_send}`", parse_mode='Markdown')
                else:
                    await query.answer("❌ Stock Empty!", show_alert=True)

            elif action == "manual":
                await query.edit_message_caption(caption=f"✍️ **Manual Mode**\nUser ID: `{user_id_int}`\n\nSend: `/send {user_id_int} YOUR_CODE`", parse_mode='Markdown')

            elif action == "reject":
                if user_id_int in PENDING_ORDERS: del PENDING_ORDERS[user_id_int]
                try: await delete_order_db(user_id_int)
                except: pass
                await query.edit_message_caption(caption=f"❌ **Rejected**\nUser ID: `{user_id_int}`", parse_mode='Markdown')
                await context.bot.send_message(chat_id=user_id_int, text="❌ **Payment Rejected!**", parse_mode='Markdown')     
        except Exception as e: print(f"Admin Error: {e}")
        return

    # --- USER SHOPPING ---
    if data == 'btn_use_all_points':
          user_id = query.from_user.id
          if user_id in PENDING_ORDERS:
            PENDING_ORDERS[user_id]['req_use_all_points'] = True
            try: await update_order_db(user_id)
            except: pass
            await query.answer("💎 Point 50% Selected")
            await query.edit_message_text(f"✅ **Point 50% သုံးမည်**\nScreenshot ပို့ပေးပါ (Caption မလိုပါ)။", parse_mode='Markdown')
          else:
            await query.answer("Session Expired", show_alert=True)
          return

    if not IS_SHOP_OPEN and update.effective_user.id != ADMIN_ID:
        await query.answer("ဆိုင်ခေတ္တပိတ်ထားပါသည်", show_alert=True)
        return

    # Navigation Logic (Region Selection)
    if data == 'steam_main':
        keyboard = [
            [InlineKeyboardButton("🇺🇸 US Region", callback_data='steam.us'), InlineKeyboardButton("🇸🇬 SG Region", callback_data='steam.sg')],
            [InlineKeyboardButton("🇮🇳 India", callback_data='steam.in'), InlineKeyboardButton("🇹🇭 Thai", callback_data='steam.th')],
            [InlineKeyboardButton("🇦🇷 Argentina", callback_data='steam.ar'), InlineKeyboardButton("🇹🇷 Turkey", callback_data='steam.tr')],
            [InlineKeyboardButton("🇨🇳 China", callback_data='steam.cn')], 
            [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]
        ]
        await query.edit_message_text("Steam Wallet Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'apple_main':
        keyboard = [
            [InlineKeyboardButton("🇺🇸 US Region", callback_data='apple.us')],
            [InlineKeyboardButton("🇸🇬 SG Region", callback_data='apple.sg')],
            [InlineKeyboardButton("🇹🇷 Turkey Region", callback_data='apple.tr')],
            [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]
        ]
        await query.edit_message_text("Apple Gift Card Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'psn_main':
        keyboard = [
            [InlineKeyboardButton("🇺🇸 US Region", callback_data='psn.us')],
            [InlineKeyboardButton("🇸🇬 SG Region", callback_data='psn.sg')],
            [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]
        ]
        await query.edit_message_text("PSN Gift Card Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
        
    if data == 'nintendo_main':
        keyboard = [
            [InlineKeyboardButton("🇺🇸 US Region", callback_data='nintendo.us')],
            [InlineKeyboardButton("🇯🇵 Japan Region", callback_data='nintendo.jp')],
            [InlineKeyboardButton("🇸🇬 SG Region", callback_data='nintendo.sg')],
            [InlineKeyboardButton("🇬🇧 UK Region", callback_data='nintendo.uk')],
            [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]
        ]
        await query.edit_message_text("Nintendo eShop Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'roblox_main':
        keyboard = [[InlineKeyboardButton("🇺🇸 US Region", callback_data='roblox.us')], [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]]
        await query.edit_message_text("Roblox Gift Card Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'visa_main':
        keyboard = [[InlineKeyboardButton("🇺🇸 US Region", callback_data='visa.us')], [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]]
        await query.edit_message_text("Visa Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'mastercard_main':
        keyboard = [[InlineKeyboardButton("🇺🇸 US Region", callback_data='mastercard.us')], [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]]
        await query.edit_message_text("Mastercard Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'tg_prem_main':
        keyboard = [[InlineKeyboardButton("🌟 Premium Gift (Global)", callback_data='tg.prem')], [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]]
        await query.edit_message_text("Telegram Premium Plan ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Amount Selection Logic
    if data in PRICES:
        category = PRICES[data]
        keyboard = []
        for amount, price in category["items"].items():
            callback_str = f"buy|{data}|{amount}|{price}"
            keyboard.append([InlineKeyboardButton(f"{amount} - {price}", callback_data=callback_str)])
        
        prefix = data.split('.')[0] 
        back_callback = f"{prefix}_main"
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=back_callback)])
        await query.edit_message_text(f"Please select {category['text']} amount:", reply_markup=InlineKeyboardMarkup(keyboard))
        return # ဒီနေရာမှာ Return ခံထားမှ အောက်က buy ဆီ မရောက်မှာ

    elif data == 'shop_main':
        await show_shop_categories(update, context)

    # --- BUYING PROCESS ---
    # ဒီနေရာမှာ Database Error တက်ရင် ရပ်မသွားအောင် try/except ခံလိုက်ပါပြီ
    elif data.startswith('buy|'):
        _, cat, amount, price = data.split('|')
        product_name = PRICES[cat]["text"]
        
        user_id = query.from_user.id
        PENDING_ORDERS[user_id] = {
            "cat": cat,
            "amt": amount,
            "price": price,
            "product_name": product_name
        }
        
        # ⚠️ CRITICAL FIX: Database မရရင်လည်း ဆက်လုပ်မယ်
        try: await update_order_db(user_id)
        except Exception as e: print(f"DB Error (Ignored): {e}")

        context.user_data['order'] = f"{product_name} ({amount}) - {price}"
        
        text = (
            f"✅ လူကြီးမင်း {product_name} ({amount}) ကို ရွေးချယ်ထားပါတယ်။\n"
            f"💰 ကျသင့်ငွေ: {price}\n\n"
            "ငွေလွှဲရန် Kpay & Wave: `09767202280`\nName = Kyaw Zin Htwe\n⚠️ Note မှာ Shop လို့ ထည့်‌ပေးပါ\n\n"
            "❗️ ငွေလွှဲပြီးပါက ဒီထဲကို Screenshot ပို့ပေးပါ။ Admin မှ စစ်ဆေးပြီး Code ပို့ပေးပါမယ်။\n"
        )
        keyboard = [[InlineKeyboardButton("💎 Point 50% သုံးမည်", callback_data='btn_use_all_points')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')



async def delete_after_delay(message, delay):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user(update.effective_user.id)
    if user_data.get("banned", False):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ **Access Denied**\n\nလူကြီးမင်း၏ အကောင့်အား Ban ထားပါသဖြင့် ဤ Bot ကို ဆက်လက်အသုံးပြု၍ မရနိုင်တော့ပါ။", parse_mode='Markdown')
        return

    user = update.message.from_user
    if user.id not in PENDING_ORDERS:
        await update.message.reply_text("⚠️ **No Order Found!**\n\nလူကြီးမင်း ဘာမှ မှာယူထားခြင်း မရှိသေးပါ။\nကျေးဇူးပြု၍ **'🛍️ ဈေးဝယ်ရန်'** ကို နှိပ်ပြီး ပစ္စည်းအရင်ရွေးချယ်ပေးပါခင်ဗျာ။", parse_mode='Markdown')
        return

    caption = update.message.caption
    item = PENDING_ORDERS[user.id]
    order_info = f"{item['product_name']} ({item['amt']}) - {item['price']}"

    # Point Logic
    points_to_use = 0
    point_msg = ""
    current_points = user_data.get("points", 0)

    if caption and caption.strip().startswith("/exch"):
        parts = caption.split()
        if len(parts) > 1 and parts[1].isdigit():
            req_points = int(parts[1])
            if req_points <= current_points: points_to_use = req_points
            else:
                await update.message.reply_text(f"⚠️ Point မလုံလောက်ပါ။ လက်ကျန်: {current_points}")
                return 
        else: points_to_use = current_points
    
    elif item.get('req_use_all_points'):
        # လက်ရှိ Point ကို ၂ နဲ့စားပြီး ကိန်းပြည့်ယူမယ် (ဥပမာ 100 ရှိရင် 50 သုံးမယ်)
        points_to_use = int(current_points / 2)


    if points_to_use > 0:
        PENDING_ORDERS[user.id]['final_point_deduct'] = points_to_use
        # အဲ့ဒါကို ဖျက်ပြီး အောက်ကဟာနဲ့ အစားထိုးပါ
        
        await update_order_db(user.id) # ✅ MongoDB Update Code
        point_msg = f"\n💎 **Exchange:** {points_to_use} Points"

    # Notify Admin
    caption_for_admin = (
        f"🔔 **New Order Received!**\n"
        f"👤 Customer: {user.first_name} (ID: `{user.id}`)\n"
        f"🛒 Item: {order_info}"
        f"{point_msg}\n"
        f"📸 Payment Screenshot Check:"
    )
    
    admin_keyboard = [[InlineKeyboardButton("✅ Accept", callback_data=f"admin|accept|{user.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"admin|reject|{user.id}")]]
    
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=caption_for_admin, reply_markup=InlineKeyboardMarkup(admin_keyboard), parse_mode='Markdown')
    
    if IS_ADMIN_ONLINE:
        msg = await update.message.reply_text("✅ Screenshot လက်ခံရရှိပါတယ်။ Admin မှ စစ်ဆေးနေပါသည်။")
        asyncio.create_task(delete_after_delay(msg, 30))
    else:
        offline_msg = (
            "📴 **Admin Offline **\n\n"
            "မင်္ဂလာပါခင်ဗျာ။ လက်ရှိအချိန်တွင် Admin သည်  Offline ဖြစ်နေပါသည်။\n\n"
            "✅ လူကြီးမင်း၏ Order ကို လက်ခံရရှိထားပြီး ဖြစ်ပါသည်။\n"
            "⏰ Admin Online ပြန်ဖြစ်သည်နှင့် ငွေလွှဲစစ်ဆေးပြီး Code ကို ချက်ချင်း ပို့ပေးပါမည်။\n\n"
            "အရေးကြီးပါက Phone ခေါလို့ရပါတယ်‌ဗျ။ စောင့်ဆိုင်းပေးလို့ ကျေးဇူးတင်ပါတယ်😘။ "
        )
        await update.message.reply_text(offline_msg, parse_mode='Markdown')
# --- HELPER: Process Successful Order ---
async def process_successful_order(update, context, user_id_int, code_text, product_name="Unknown Item"):
    user_id_str = str(user_id_int)
   
   # Add Points & Referrer Bonus
    if user_id_str in USER_DB:
        USER_DB[user_id_str]["points"] += 100
        await context.bot.send_message(chat_id=user_id_int, text="🎉 **Congratulations!**\nဝယ်ယူမှု အောင်မြင်သည့်အတွက် **1️⃣0️⃣0️⃣ Points** ရရှိပါသည်။", parse_mode='Markdown')
    
    buyer_data = USER_DB.get(user_id_str, {})
    referrer_id = buyer_data.get("invited_by")
    
    # Referrer ရှိမှသာ အလုပ်လုပ်မည်
    if referrer_id and referrer_id in USER_DB:
        USER_DB[referrer_id]["points"] += 100
        
        # 👇 ဒီကောင်က if ကွင်းထဲမှာ ရှိနေမှရပါမယ်
        await update_user_db(referrer_id)
            
        try: 
            await context.bot.send_message(chat_id=int(referrer_id), text=f"🎉 **Referral Bonus!**\nသင် Invite ထားသော သူငယ်ချင်းမှ ဈေးဝယ်ယူမှု အောင်မြင်သည့်အတွက် သင့်အကောင့်ထဲသို့ **100 Points** ထပ်ပေါင်းထည့်ပေးလိုက်ပါပြီ။")
        except: 
            pass 
    
    # ဝယ်သူရဲ့ Data ကို Update လုပ်မယ်
    await update_user_db(user_id_str)

    # SAVE HISTORY (New)
    await save_to_history(user_id_str, product_name, code_text)

    # Send Code
    # 👇 ဒီအောက်က စာကြောင်းတွေက Function ထဲ (ညာဘက်) မှာ ရှိနေရပါမယ်
    msg_to_user = (
        "✅ **Order Completed!**\n\n"
        "လူကြီးမင်း ဝယ်ယူထားသော Code ရရှိပါပြီ။\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"`{code_text}`\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "အားပေးမှုကို ကျေးဇူးတင်ပါတယ်။"
    )
    await context.bot.send_message(chat_id=user_id_int, text=msg_to_user, parse_mode='Markdown')

    
    if user_id_int in PENDING_ORDERS:
        del PENDING_ORDERS[user_id_int]
        # 👇 (၁) del နဲ့ တစ်တန်းတည်း ဖြစ်သွားပါပြီ
        await delete_order_db(user_id_int)

    # Show Menu (Simplified)
    # 👇 (၂) ဒီအောက်က စာကြောင်းတွေကလည်း ညာဘက် (Function အတွင်း) မှာ ရှိနေရပါမယ်
    simple_keyboard = [
        [InlineKeyboardButton("🛍️ ဈေးဝယ်ရန်", callback_data='shop_main')]
    ]
    
    await context.bot.send_message(
        chat_id=user_id_int, 
        text="🛍️ နောက်ထပ် ဝယ်ယူလိုပါက နှိပ်ပါ -", 
        reply_markup=InlineKeyboardMarkup(simple_keyboard)
    )


# --- MANUAL COMMANDS ---
async def send_code_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    try:
        user_id = int(context.args[0])
        code_text = " ".join(context.args[1:])
        
        # User မှာထားတာ ရှိ/မရှိ စစ်မယ်
        item_name = "Manual Send Item" # ပုံမှန် နာမည်
        
        if user_id in PENDING_ORDERS:
            order = PENDING_ORDERS[user_id]
            # မှာထားတာရှိရင် နာမည်နဲ့ ပမာဏကို ယူမယ်
            # Output ပုံစံ: Manual Send Item (အောက်တစ်ကြောင်းဆင်း) Steam US $5
            item_name = f"Manual Send Item\n{order['product_name']} {order['amt']}"
            
        await process_successful_order(update, context, user_id, code_text, item_name)
        await update.message.reply_text(f"✅ User (ID: {user_id}) ဆီ Code (Manual) ပို့ပြီးပါပြီ။")
        
    except Exception as e: await update.message.reply_text(f"Error: {e}")


async def add_stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("Format: `/addstock <type> <amount> <code>`", parse_mode='Markdown')
            return
        
        category = args[0]
        code = args[-1]
        amount = " ".join(args[1:-1])
        
        if category not in PRICES:
            await update.message.reply_text("❌ Category Error: PRICES list ထဲတွင်ပြန်စစ်ပါ။")
            return
            
        key = f"{category}|{amount}"
        if key not in STOCKS: STOCKS[key] = []
        STOCKS[key].append(code)
       # key ဆိုတာ အပေါ်နားမှာ သတ်မှတ်ထားတဲ့ (ဥပမာ steam.us|$5) key ပါ
        await update_stock_db(key)

        await update.message.reply_text(f"✅ Stock Added!\nItem: `{key}`\nCount: {len(STOCKS[key])}", parse_mode='Markdown')
    except Exception as e: await update.message.reply_text(f"Error: {e}")

# --- POINTS & ADMIN CMD ---
async def remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        user_id = context.args[0]
        amount = int(context.args[1])
        if user_id in USER_DB:
            USER_DB[user_id]["points"] -= amount
            # user_id ဆိုတာ Point နှုတ်ခံရတဲ့သူရဲ့ ID ပါ
            await update_user_db(user_id)

            await update.message.reply_text(f"✅ Removed {amount} points from {user_id}")
            try: await context.bot.send_message(chat_id=int(user_id), text=f"📢 **Point Deduction Alert**\nPoint **{amount}** အား Admin မှ နှုတ်ယူလိုက်ပါသည်။", parse_mode='Markdown')
            except: pass
    except: pass

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = context.args[0]
        amount = int(context.args[1])
        if target_id not in USER_DB:                                 USER_DB[target_id] = {"points": 0, "invited_by": None, "referrals": 0, "banned": False}
        USER_DB[target_id]["points"] += amount
      # target_id ဆိုတာ Point ရမည့်သူရဲ့ ID ပါ (ဒီ function မှာ variable နာမည်က target_id ပါ)
        await update_user_db(target_id)

        await update.message.reply_text(f"✅ User `{target_id}` သို့ {amount} Points ထည့်ပေးလိုက်ပါပြီ။", parse_mode='Markdown')
        try: await context.bot.send_message(chat_id=int(target_id), text=f"🎉 **Points Received!**\nAdmin မှ လူကြီးမင်း၏ အကောင့်ထဲသို့ **{amount} Points** ထပ်ဖြည့်ပေးလိုက်ပါပြီ။", parse_mode='Markdown')
        except: pass
    except: pass

async def top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    sorted_users = sorted(USER_DB.items(), key=lambda x: x[1]['points'], reverse=True)[:5]
    msg = "🏆 **Top 5 Point Earners** 🏆\n➖➖➖➖➖➖➖➖➖➖\n"
    for i, (uid, data) in enumerate(sorted_users, 1): msg += f"{i}. ID: `{uid}` \n    💰 Points: **{data['points']}**\n\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def set_offline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    global IS_ADMIN_ONLINE
    IS_ADMIN_ONLINE = False
    await update.message.reply_text("💤 **Admin Offline Mode Activated!**", parse_mode='Markdown')

async def set_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    global IS_ADMIN_ONLINE
    IS_ADMIN_ONLINE = True
    await update.message.reply_text("☀️ **Admin Online!**", parse_mode='Markdown')
    
    # --- MASTER BUTTON HANDLER (ခလုတ်အားလုံးကို ထိန်းချုပ်မည့်နေရာ) ---
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    # Loading လည်တာ ရပ်မယ်
    await query.answer()

    # (၁) ပင်မ Menu သို့ ပြန်သွားရန်
    if data == 'shop_main':
        await show_shop_categories(update, context)

    # (၂) Steam နိုင်ငံရွေးရန်
    elif data == 'steam_main':
        keyboard = [
            [InlineKeyboardButton("🇺🇸 US Region", callback_data='steam.us')],
            [InlineKeyboardButton("🇸🇬 SG Region", callback_data='steam.sg')],
            [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]
        ]
        await query.edit_message_text("Steam Wallet Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
    # --- MISSING CATEGORIES (ဒီကောင်တွေ ကျန်နေလို့ပါ) ---
    
    if data == 'apple_main':
        keyboard = [
            [InlineKeyboardButton("🇺🇸 US Region", callback_data='apple.us')],
            [InlineKeyboardButton("🇸🇬 SG Region", callback_data='apple.sg')],
            [InlineKeyboardButton("🇹🇷 Turkey Region", callback_data='apple.tr')],
            [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]
        ]
        await query.edit_message_text("Apple Gift Card Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'psn_main':
        keyboard = [
            [InlineKeyboardButton("🇺🇸 US Region", callback_data='psn.us')],
            [InlineKeyboardButton("🇸🇬 SG Region", callback_data='psn.sg')],
            [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]
        ]
        await query.edit_message_text("PSN Gift Card Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == 'nintendo_main':
        keyboard = [
            [InlineKeyboardButton("🇺🇸 US Region", callback_data='nintendo.us')],
            [InlineKeyboardButton("🇯🇵 Japan Region", callback_data='nintendo.jp')],
            [InlineKeyboardButton("🇸🇬 SG Region", callback_data='nintendo.sg')],
            [InlineKeyboardButton("🇬🇧 UK Region", callback_data='nintendo.uk')],
            [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]
        ]
        await query.edit_message_text("Nintendo eShop Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'roblox_main':
        keyboard = [
            [InlineKeyboardButton("🇺🇸 US Region", callback_data='roblox.us')],
            [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]
        ]
        await query.edit_message_text("Roblox Gift Card Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'visa_main':
        keyboard = [[InlineKeyboardButton("🇺🇸 US Region", callback_data='visa.us')],
                    [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]]
        await query.edit_message_text("Visa Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'mastercard_main':
        keyboard = [[InlineKeyboardButton("🇺🇸 US Region", callback_data='mastercard.us')],
                    [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]]
        await query.edit_message_text("Mastercard Region ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'tg_prem_main':
        keyboard = [
            [InlineKeyboardButton("🌟 Premium Gift (Global)", callback_data='tg.prem')],
            [InlineKeyboardButton("🔙 Back", callback_data='shop_main')]
        ]
        await query.edit_message_text("Telegram Premium Plan ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))

    # (၃) ဈေးနှုန်းပြရန် (Steam US)
        # --- GENERIC PRICE HANDLER (ဒါထည့်လိုက်ရင် အကုန်ရပြီ) ---
    elif data in PRICES:
        category = PRICES[data]
        keyboard = []
        for amount, price in category["items"].items():
            # Button Data ပြင်ဆင်ခြင်း
            callback_str = f"buy|{data}|{amount}|{price}"
            keyboard.append([InlineKeyboardButton(f"{amount} - {price}", callback_data=callback_str)])
        
        # Back Button အတွက် Logic
        prefix = data.split('.')[0] 
        back_callback = f"{prefix}_main"
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=back_callback)])
              
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Please select {category['text']} amount:", reply_markup=reply_markup)

    # (၄) ဝယ်ယူမှု စတင်ရန် (Buying Process)
    elif data.startswith('buy|'):
        # Data ဖြည်မယ် (Example: buy|steam.us|$5|23,000 Ks)
        _, cat, amount, price = data.split('|')
        product_name = PRICES[cat]["text"]
        
        user_id = query.from_user.id
        
        # Order အဖြစ် မှတ်သားမယ်
        PENDING_ORDERS[user_id] = {
            "cat": cat,
            "amt": amount,
            "price": price,
            "product_name": product_name
        }
        await update_order_db(user_id) # Database ထဲထည့်မယ်

        # အတည်ပြုစာ ပို့မယ်
        text = (
            f"✅ လူကြီးမင်း **{product_name} ({amount})** ကို ရွေးချယ်ထားပါတယ်။\n"
            f"💰 ကျသင့်ငွေ: **{price}**\n\n"
            "ငွေလွှဲရန် Kpay & Wave: `09767202280`\n"
            "Name: Kyaw Zin Htwe\n"
            "⚠️ Note မှာ **Shop** လို့ ထည့်‌ပေးပါနော်\n\n"
            "❗️ ငွေလွှဲပြီးပါက ဒီထဲကို Screenshot ပို့ပေးပါ။ Admin မှ စစ်ဆေးပြီး Code ပို့ပေးပါမယ်။"
        )
        
        # Point သုံးမလား မေးတဲ့ ခလုတ်
        keyboard = [[InlineKeyboardButton("💎 Point 50% သုံးမည်", callback_data='btn_use_all_points')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # (၅) Point သုံးလျှင်
    elif data == 'btn_use_all_points':
         await query.answer("Point စနစ် ပြုပြင်နေဆဲဖြစ်ပါသည်...", show_alert=True)
         # ဒီနေရာမှာ Point နှုတ်တဲ့ Logic တွေ လာထည့်လို့ရပါတယ်


if if __name__ == '__main__':
    # 👇 ၁။ ဒီကောင်ကို အရင်ဆုံး စ run ခိုင်းရပါမယ် (ဒါမှ Port ပွင့်မှာပါ)
    keep_alive()
    # post_init ကို ဒီနေရာမှာ ထည့်လိုက်ပါပြီ
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    prefixes = ['.', '/']

    # --- ADMIN COMMANDS ---
    application.add_handler(PrefixHandler(prefixes, 'online', set_online))
    application.add_handler(PrefixHandler(prefixes, 'offline', set_offline))
    application.add_handler(PrefixHandler(prefixes, 'openshop', open_shop))
    application.add_handler(PrefixHandler(prefixes, 'closeshop', close_shop))
    application.add_handler(PrefixHandler(prefixes, 'addpromo', add_promo))
    
    # --- ADMIN DASHBOARD ---
    application.add_handler(PrefixHandler(prefixes, 'stats', admin_dashboard))
    application.add_handler(PrefixHandler(prefixes, 'cast', admin_dashboard))
    application.add_handler(PrefixHandler(prefixes, 'msg', admin_dashboard))
    
    # --- POINTS & BAN ---
    application.add_handler(PrefixHandler(prefixes, 'removepoint', remove_points))
    application.add_handler(PrefixHandler(prefixes, 'addpoint', add_points)) 
    application.add_handler(PrefixHandler(prefixes, 'topuser', top_users)) 
    application.add_handler(PrefixHandler(prefixes, 'ban', ban_user))
    application.add_handler(PrefixHandler(prefixes, 'unban', unban_user))
    application.add_handler(PrefixHandler(prefixes, 'addstock', add_stock_command))
    application.add_handler(PrefixHandler(prefixes, 'send', send_code_to_user))
    application.add_handler(PrefixHandler(prefixes, 'backup', force_backup)) 
    
    # --- USER COMMANDS ---
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('shop', shop_command))      
    application.add_handler(CommandHandler('account', account_command)) 
    application.add_handler(CommandHandler('contact', contact_command)) 
    application.add_handler(CommandHandler('myorders', my_orders))
    application.add_handler(CommandHandler('redeem', redeem_promo))
    
    application.add_handler(PrefixHandler(prefixes, 'myorders', my_orders))
    application.add_handler(PrefixHandler(prefixes, 'redeem', redeem_promo))

    # --- TEXT & CALLBACK ---
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    application.add_handler(CallbackQueryHandler(menu_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo)) 

    # --- JOB QUEUE (AUTO BACKUP) ---
    # 43200 seconds = 12 Hours (၁၂ နာရီတစ်ခါ Backup လုပ်မယ်)
    if application.job_queue:
        application.job_queue.run_repeating(auto_backup_job, interval=43200, first=10)
        print("✅ Auto Backup System Started...")

    print("Bot is running...")
    
    # Connection ကျရင် သူ့အလိုလို ပြန်ချိတ်ပါလိမ့်မယ်
    application.run_polling()
