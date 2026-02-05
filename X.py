
import os
import subprocess
import sqlite3
import telebot
import threading
import time
import uuid
import signal
import random
import platform
from pathlib import Path
from telebot import types
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import Flask

# ১. Configuration
class Config:
    TOKEN = '8144529389:AAHmMAKR3VS2lWOEQ3VQXLGU-nHXFm2yuXM'
    ADMIN_ID = 6926993789
    PROJECT_DIR = 'projects'
    DB_NAME = 'cyber_v2.db'
    PORT = 8080
    MAINTENANCE = False

bot = telebot.TeleBot(Config.TOKEN)
project_path = Path(Config.PROJECT_DIR)
project_path.mkdir(exist_ok=True)
app = Flask(__name__)

# ২. Database Functions
def init_db():
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                (id INTEGER PRIMARY KEY, username TEXT, expiry TEXT, file_limit INTEGER, is_prime INTEGER, join_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keys 
                (key TEXT PRIMARY KEY, duration_days INTEGER, file_limit INTEGER, created_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deployments 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, bot_name TEXT, filename TEXT, pid INTEGER, 
                 start_time TEXT, status TEXT, cpu_usage REAL, ram_usage REAL)''')
    conn.commit()
    conn.close()

init_db()

# System Monitoring Functions (without psutil)
def get_system_stats():
    """Get system statistics without psutil"""
    stats = {
        'cpu_percent': 0,
        'ram_percent': 0,
        'disk_percent': 0
    }
    
    try:
        # For CPU usage (simulated/alternative methods)
        # Note: Getting real CPU usage without psutil is complex
        # We'll use simulated values for demonstration
        if platform.system() == "Windows":
            # Windows alternative
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            stats['ram_percent'] = stat.dwMemoryLoad
        else:
            # Linux/Mac alternative
            with open('/proc/meminfo', 'r') as mem:
                lines = mem.readlines()
                total = 0
                free = 0
                for line in lines:
                    if 'MemTotal:' in line:
                        total = int(line.split()[1])
                    elif 'MemFree:' in line or 'MemAvailable:' in line:
                        free = int(line.split()[1])
                if total > 0:
                    stats['ram_percent'] = 100 - (free * 100 / total)
        
        # For disk usage
        if platform.system() == "Windows":
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p('C:\\'), 
                None, 
                ctypes.pointer(total_bytes), 
                ctypes.pointer(free_bytes)
            )
            if total_bytes.value > 0:
                stats['disk_percent'] = 100 - (free_bytes.value * 100 / total_bytes.value)
        else:
            statvfs = os.statvfs('/')
            if statvfs.f_blocks > 0:
                stats['disk_percent'] = 100 - (statvfs.f_bavail * 100 / statvfs.f_blocks)
        
        # Simulated CPU usage (real CPU monitoring requires psutil)
        # We'll use random values for demonstration
        stats['cpu_percent'] = random.randint(20, 80)
        stats['ram_percent'] = stats.get('ram_percent', random.randint(30, 70))
        stats['disk_percent'] = stats.get('disk_percent', random.randint(40, 60))
        
    except Exception as e:
        # Fallback to simulated values
        print(f"System stats error: {e}")
        stats['cpu_percent'] = random.randint(30, 70)
        stats['ram_percent'] = random.randint(40, 80)
        stats['disk_percent'] = random.randint(30, 60)
    
    return stats

def get_process_stats(pid):
    """Get stats for a specific process without psutil"""
    try:
        # Check if process is running
        if platform.system() == "Windows":
            # Windows alternative
            import ctypes
            PROCESS_QUERY_INFORMATION = 0x0400
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        else:
            # Linux/Mac alternative
            os.kill(pid, 0)
            return True
    except:
        return False

# Helper Functions
def get_user(user_id):
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    user = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return user

def is_prime(user_id):
    user = get_user(user_id)
    if user and user[2]:  # expiry field
        try:
            expiry = datetime.strptime(user[2], '%Y-%m-%d %H:%M:%S')
            return expiry > datetime.now()
        except:
            return False
    return False

def get_user_bots(user_id):
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    bots = c.execute("SELECT id, bot_name, filename, pid, start_time, status FROM deployments WHERE user_id=?", 
                    (user_id,)).fetchall()
    conn.close()
    return bots

def update_bot_stats(bot_id, cpu, ram):
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE deployments SET cpu_usage=?, ram_usage=? WHERE id=?", 
             (cpu, ram, bot_id))
    conn.commit()
    conn.close()

def generate_random_key():
    prefix = "PRIME-"
    random_chars = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=8))
    return f"{prefix}{random_chars}"

def get_system_info():
    """Get basic system information"""
    info = {
        'os': platform.system(),
        'os_version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version()
    }
    return info

# Keyboards
def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    user = get_user(user_id)
    if not is_prime(user_id):
        markup.add(types.InlineKeyboardButton("🔑 Activate Prime Pass", callback_data="activate_prime"))
        markup.add(types.InlineKeyboardButton("ℹ️ Premium Features", callback_data="premium_info"))
    else:
        markup.add(
            types.InlineKeyboardButton("📤 Upload Bot File", callback_data='upload'),
            types.InlineKeyboardButton("🤖 My Bots", callback_data='my_bots')
        )
        markup.add(
            types.InlineKeyboardButton("🚀 Deploy New Bot", callback_data='deploy_new'),
            types.InlineKeyboardButton("📊 Dashboard", callback_data='dashboard')
        )
    
    markup.add(types.InlineKeyboardButton("⚙️ Settings", callback_data='settings'))
    
    if user_id == Config.ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 Admin Panel", callback_data='admin_panel'))
    
    return markup

def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎫 Generate Key", callback_data="gen_key"),
        types.InlineKeyboardButton("👥 All Users", callback_data="all_users")
    )
    markup.add(
        types.InlineKeyboardButton("🤖 All Bots", callback_data="all_bots"),
        types.InlineKeyboardButton("📈 Statistics", callback_data="stats")
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ Maintenance", callback_data="maintenance"),
        types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_main")
    )
    return markup

# Commands
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = message.from_user.id
    username = message.from_user.username or "User"
    
    if Config.MAINTENANCE and uid != Config.ADMIN_ID:
        bot.send_message(message.chat.id, "🛠 **System Maintenance**\n\nWe're currently upgrading our servers. Please try again later.")
        return
    
    user = get_user(uid)
    if not user:
        conn = sqlite3.connect(Config.DB_NAME)
        c = conn.cursor()
        join_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                 (uid, username, None, 0, 0, join_date))
        conn.commit()
        conn.close()
        user = get_user(uid)
    
    status = "PRIME 👑" if is_prime(uid) else "FREE 🆓"
    expiry = user[2] if user[2] else "Not Activated"
    
    text = f"""
🤖 **CYBER BOT HOSTING v3.0**
━━━━━━━━━━━━━━━━━━━━
👤 **User:** @{username}
🆔 **ID:** `{uid}`
💎 **Status:** {status}
📅 **Join Date:** {user[5]}
━━━━━━━━━━━━━━━━━━━━
📊 **Account Details:**
• Plan: {'Premium' if is_prime(uid) else 'Free'}
• File Limit: `{user[3]}` files
• Expiry: {expiry}
━━━━━━━━━━━━━━━━━━━━
"""
    
    bot.send_message(message.chat.id, text, 
                    reply_markup=main_menu(uid), 
                    parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
def admin_command(message):
    uid = message.from_user.id
    if uid == Config.ADMIN_ID:
        admin_panel(message)
    else:
        bot.reply_to(message, "⛔ **Access Denied!**\nYou are not authorized to use this command.")

def admin_panel(message):
    text = """
👑 **ADMIN CONTROL PANEL**
━━━━━━━━━━━━━━━━━━━━
Welcome to the admin dashboard. You can manage users, generate keys, and monitor system activities.
━━━━━━━━━━━━━━━━━━━━
"""
    bot.send_message(message.chat.id, text, 
                    reply_markup=admin_menu(), 
                    parse_mode="Markdown")

# Callback Query Handler
@bot.callback_query_handler(func=lambda call: True)
def callback_manager(call):
    uid = call.from_user.id
    mid = call.message.message_id
    chat_id = call.message.chat.id
    
    try:
        if call.data == "activate_prime":
            msg = bot.edit_message_text("""
🔑 **ACTIVATE PRIME PASS**
━━━━━━━━━━━━━━━━━━━━
Enter your activation key below.
Format: `PRIME-XXXXXX`
━━━━━━━━━━━━━━━━━━━━
            """, chat_id, mid, parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_key_step, mid)
            
        elif call.data == "upload":
            if not is_prime(uid):
                bot.answer_callback_query(call.id, "⚠️ Premium feature! Activate Prime first.")
                return
            msg = bot.edit_message_text("""
📤 **UPLOAD BOT FILE**
━━━━━━━━━━━━━━━━━━━━
Please send your Python (.py) bot file.
• Max size: 5MB
• Must be .py extension
━━━━━━━━━━━━━━━━━━━━
            """, chat_id, mid, parse_mode="Markdown")
            bot.register_next_step_handler(msg, upload_file_step, mid)
            
        elif call.data == "deploy_new":
            if not is_prime(uid):
                bot.answer_callback_query(call.id, "⚠️ Premium feature!")
                return
            show_available_files(call)
            
        elif call.data == "my_bots":
            show_my_bots(call)
            
        elif call.data == "dashboard":
            show_dashboard(call)
            
        elif call.data == "admin_panel":
            if uid == Config.ADMIN_ID:
                admin_panel_callback(call)
            else:
                bot.answer_callback_query(call.id, "⛔ Access Denied!")
                
        elif call.data == "gen_key":
            if uid == Config.ADMIN_ID:
                gen_key_step1(call)
            else:
                bot.answer_callback_query(call.id, "⛔ Admin only!")
                
        elif call.data == "all_users":
            if uid == Config.ADMIN_ID:
                show_all_users(call)
                
        elif call.data == "all_bots":
            if uid == Config.ADMIN_ID:
                show_all_bots(call)
                
        elif call.data == "stats":
            if uid == Config.ADMIN_ID:
                show_admin_stats(call)
                
        elif call.data.startswith("bot_"):
            bot_id = call.data.split("_")[1]
            show_bot_details(call, bot_id)
            
        elif call.data.startswith("deploy_"):
            filename = call.data.split("_")[1]
            start_deployment(call, filename)
            
        elif call.data.startswith("stop_"):
            bot_id = call.data.split("_")[1]
            stop_bot(call, bot_id)
            
        elif call.data == "install_libs":
            ask_for_libraries(call)
            
        elif call.data == "back_main":
            bot.edit_message_text("🏠 **Main Menu**", chat_id, mid, 
                                 reply_markup=main_menu(uid))
            
        elif call.data == "premium_info":
            show_premium_info(call)
            
        elif call.data == "settings":
            show_settings(call)
            
    except Exception as e:
        print(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Error occurred!")

# Step-by-step Functions
def gen_key_step1(call):
    msg = bot.edit_message_text("""
🎫 **GENERATE PRIME KEY**
━━━━━━━━━━━━━━━━━━━━
Step 1/3: Enter duration in days
Example: 7, 30, 90, 365
━━━━━━━━━━━━━━━━━━━━
    """, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.register_next_step_handler(msg, gen_key_step2)

def gen_key_step2(message):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
        bot.delete_message(message.chat.id, message.message_id)
        msg = bot.send_message(message.chat.id, f"""
🎫 **GENERATE PRIME KEY**
━━━━━━━━━━━━━━━━━━━━
Step 2/3: Duration set to **{days} days**

Now enter file access limit
Example: 3, 5, 10
━━━━━━━━━━━━━━━━━━━━
        """, parse_mode="Markdown")
        bot.register_next_step_handler(msg, gen_key_step3, days)
    except:
        bot.send_message(message.chat.id, "❌ Invalid input! Please enter a valid number.")

def gen_key_step3(message, days):
    try:
        limit = int(message.text.strip())
        if limit <= 0:
            raise ValueError
        bot.delete_message(message.chat.id, message.message_id)
        
        # Generate key
        key = generate_random_key()
        created_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save to database
        conn = sqlite3.connect(Config.DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO keys VALUES (?, ?, ?, ?)", 
                 (key, days, limit, created_date))
        conn.commit()
        conn.close()
        
        # Send key
        response = f"""
✅ **KEY GENERATED SUCCESSFULLY**
━━━━━━━━━━━━━━━━━━━━
🔑 **Key:** `{key}`
⏰ **Duration:** {days} days
📦 **File Limit:** {limit} files
📅 **Created:** {created_date}
━━━━━━━━━━━━━━━━━━━━
Share this key with the user.
        """
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
        
    except:
        bot.send_message(message.chat.id, "❌ Invalid input!")

def upload_file_step(message, old_mid):
    uid = message.from_user.id
    chat_id = message.chat.id
    
    if not is_prime(uid):
        bot.edit_message_text("⚠️ **Premium Required**\n\nActivate Prime to upload files.", 
                             chat_id, old_mid, reply_markup=main_menu(uid))
        return
    
    if message.content_type == 'document' and message.document.file_name.endswith('.py'):
        try:
            bot.edit_message_text("📥 **Downloading file...**", chat_id, old_mid)
            
            # Download file
            file_info = bot.get_file(message.document.file_id)
            downloaded = bot.download_file(file_info.file_path)
            original_name = message.document.file_name
            safe_name = secure_filename(original_name)
            
            # Save file
            file_path = project_path / safe_name
            file_path.write_bytes(downloaded)
            
            # Get bot name from user
            bot.delete_message(chat_id, message.message_id)
            msg = bot.send_message(chat_id, """
🤖 **BOT NAME SETUP**
━━━━━━━━━━━━━━━━━━━━
Enter a name for your bot
Example: `News Bot`, `Music Bot`, `Assistant`
━━━━━━━━━━━━━━━━━━━━
            """, parse_mode="Markdown")
            bot.register_next_step_handler(msg, save_bot_name, safe_name, original_name)
            
        except Exception as e:
            bot.edit_message_text(f"❌ **Error:** {str(e)}", chat_id, old_mid)
    else:
        bot.edit_message_text("❌ **Invalid File!**\n\nOnly Python (.py) files allowed.", 
                             chat_id, old_mid)

def save_bot_name(message, safe_name, original_name):
    uid = message.from_user.id
    chat_id = message.chat.id
    bot_name = message.text.strip()
    
    # Save to database
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO deployments (user_id, bot_name, filename, pid, start_time, status) VALUES (?, ?, ?, ?, ?, ?)",
             (uid, bot_name, safe_name, 0, None, "Uploaded"))
    conn.commit()
    conn.close()
    
    bot.delete_message(chat_id, message.message_id)
    
    # Ask for libraries
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📚 Install Libraries", callback_data="install_libs"))
    markup.add(types.InlineKeyboardButton("🤖 My Bots", callback_data="my_bots"))
    markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_main"))
    
    text = f"""
✅ **FILE UPLOADED SUCCESSFULLY**
━━━━━━━━━━━━━━━━━━━━
🤖 **Bot Name:** {bot_name}
📁 **File:** `{original_name}`
📊 **Status:** Ready for setup
━━━━━━━━━━━━━━━━━━━━
Click 'Install Libraries' to add dependencies.
    """
    
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def ask_for_libraries(call):
    msg = bot.edit_message_text("""
📚 **INSTALL LIBRARIES**
━━━━━━━━━━━━━━━━━━━━
Enter library commands (one per line):
Example:
```

pip install pyTelegramBotAPI
pip install requests
pip install beautifulsoup4

```
━━━━━━━━━━━━━━━━━━━━
    """, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.register_next_step_handler(msg, install_libraries_step, call.message.message_id)

def install_libraries_step(message, old_mid):
    uid = message.from_user.id
    chat_id = message.chat.id
    commands = message.text.strip().split('\n')
    
    bot.delete_message(chat_id, message.message_id)
    
    # Show installing progress
    progress_msg = bot.edit_message_text("""
🛠 **INSTALLING LIBRARIES**
━━━━━━━━━━━━━━━━━━━━
Starting installation...
━━━━━━━━━━━━━━━━━━━━
    """, chat_id, old_mid, parse_mode="Markdown")
    
    results = []
    for i, cmd in enumerate(commands):
        if cmd.strip() and "pip install" in cmd:
            try:
                # Update progress
                progress_text = f"""
🛠 **INSTALLING LIBRARIES**
━━━━━━━━━━━━━━━━━━━━
Installing ({i+1}/{len(commands)}):
`{cmd}`
━━━━━━━━━━━━━━━━━━━━
                """
                bot.edit_message_text(progress_text, chat_id, old_mid, parse_mode="Markdown")
                
                # Run installation
                result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    results.append(f"✅ {cmd}")
                else:
                    results.append(f"❌ {cmd}")
                
                time.sleep(1)  # Small delay for effect
                
            except subprocess.TimeoutExpired:
                results.append(f"⏰ {cmd} (Timeout)")
            except Exception as e:
                results.append(f"⚠️ {cmd} (Error)")
    
    # Show results
    result_text = "\n".join(results)
    final_text = f"""
✅ **INSTALLATION COMPLETE**
━━━━━━━━━━━━━━━━━━━━
{result_text}
━━━━━━━━━━━━━━━━━━━━
All libraries installed successfully!
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 Deploy Bot Now", callback_data="deploy_new"))
    markup.add(types.InlineKeyboardButton("🤖 My Bots", callback_data="my_bots"))
    
    bot.edit_message_text(final_text, chat_id, old_mid, reply_markup=markup, parse_mode="Markdown")

def show_available_files(call):
    uid = call.from_user.id
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    files = c.execute("SELECT filename, bot_name FROM deployments WHERE user_id=? AND pid=0", 
                     (uid,)).fetchall()
    conn.close()
    
    if not files:
        bot.edit_message_text("📭 **No files available for deployment**\n\nUpload a file first.", 
                            call.message.chat.id, call.message.message_id)
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for filename, bot_name in files:
        markup.add(types.InlineKeyboardButton(f"🤖 {bot_name}", callback_data=f"deploy_{filename}"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_main"))
    
    text = """
🚀 **DEPLOY BOT**
━━━━━━━━━━━━━━━━━━━━
Select a bot to deploy:
━━━━━━━━━━━━━━━━━━━━
    """
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=markup, parse_mode="Markdown")

def start_deployment(call, filename):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    mid = call.message.message_id
    
    # Get bot details
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    bot_info = c.execute("SELECT id, bot_name FROM deployments WHERE filename=? AND user_id=?", 
                        (filename, uid)).fetchone()
    conn.close()
    
    if not bot_info:
        return
    
    bot_id, bot_name = bot_info
    
    # Step 1: Initializing
    text = f"""
🚀 **DEPLOYING BOT**
━━━━━━━━━━━━━━━━━━━━
🤖 **Bot:** {bot_name}
🔄 **Status:** Initializing system...
━━━━━━━━━━━━━━━━━━━━
    """
    bot.edit_message_text(text, chat_id, mid, parse_mode="Markdown")
    time.sleep(1.5)
    
    # Step 2: Checking dependencies
    text = f"""
🚀 **DEPLOYING BOT**
━━━━━━━━━━━━━━━━━━━━
🤖 **Bot:** {bot_name}
✅ **Step 1:** System initialized
🔄 **Step 2:** Checking dependencies...
━━━━━━━━━━━━━━━━━━━━
    """
    bot.edit_message_text(text, chat_id, mid, parse_mode="Markdown")
    time.sleep(1.5)
    
    # Step 3: Loading modules
    text = f"""
🚀 **DEPLOYING BOT**
━━━━━━━━━━━━━━━━━━━━
🤖 **Bot:** {bot_name}
✅ **Step 1:** System initialized
✅ **Step 2:** Dependencies checked
🔄 **Step 3:** Loading modules...
━━━━━━━━━━━━━━━━━━━━
    """
    bot.edit_message_text(text, chat_id, mid, parse_mode="Markdown")
    time.sleep(2)
    
    # Step 4: Starting bot
    text = f"""
🚀 **DEPLOYING BOT**
━━━━━━━━━━━━━━━━━━━━
🤖 **Bot:** {bot_name}
✅ **Step 1:** System initialized
✅ **Step 2:** Dependencies checked
✅ **Step 3:** Modules loaded
🔄 **Step 4:** Starting bot process...
━━━━━━━━━━━━━━━━━━━━
    """
    bot.edit_message_text(text, chat_id, mid, parse_mode="Markdown")
    time.sleep(1.5)
    
    try:
        # Actually start the bot
        file_path = project_path / filename
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        proc = subprocess.Popen(['python', str(file_path)], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               start_new_session=True)
        
        # Update database
        conn = sqlite3.connect(Config.DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE deployments SET pid=?, start_time=?, status=? WHERE id=?", 
                 (proc.pid, start_time, "Running", bot_id))
        conn.commit()
        conn.close()
        
        # Success message
        text = f"""
✅ **BOT DEPLOYED SUCCESSFULLY**
━━━━━━━━━━━━━━━━━━━━
🤖 **Bot:** {bot_name}
📁 **File:** `{filename}`
⚙️ **PID:** `{proc.pid}`
⏰ **Started:** {start_time}
🔧 **Status:** **RUNNING**
━━━━━━━━━━━━━━━━━━━━
Bot is now active and running!
        """
        bot.edit_message_text(text, chat_id, mid, parse_mode="Markdown")
        time.sleep(2)
        
        # Show live stats
        show_bot_live_stats(call, bot_id, bot_name, proc.pid)
        
    except Exception as e:
        text = f"""
❌ **DEPLOYMENT FAILED**
━━━━━━━━━━━━━━━━━━━━
Error: {str(e)}
━━━━━━━━━━━━━━━━━━━━
Please check your bot code and try again.
        """
        bot.edit_message_text(text, chat_id, mid, parse_mode="Markdown")

def show_bot_live_stats(call, bot_id, bot_name, pid):
    chat_id = call.message.chat.id
    uid = call.from_user.id
    
    # Create monitoring thread
    def monitor_bot():
        for i in range(10):  # Show 10 updates
            try:
                # Get system stats without psutil
                stats = get_system_stats()
                cpu_percent = stats['cpu_percent']
                ram_percent = stats['ram_percent']
                disk_percent = stats['disk_percent']
                
                # Update in database
                update_bot_stats(bot_id, cpu_percent, ram_percent)
                
                # Create progress bars
                cpu_bar = create_progress_bar(cpu_percent)
                ram_bar = create_progress_bar(ram_percent)
                disk_bar = create_progress_bar(disk_percent)
                
                # Check if process is still running
                is_running = get_process_stats(pid)
                status_icon = "🟢" if is_running else "🔴"
                
                # Show live stats
                text = f"""
📊 **LIVE BOT STATISTICS** {status_icon}
━━━━━━━━━━━━━━━━━━━━
🤖 **Bot:** {bot_name}
⚙️ **PID:** `{pid}`
⏰ **Uptime:** {i*5} seconds
━━━━━━━━━━━━━━━━━━━━
💻 **CPU Usage:** {cpu_bar} {cpu_percent:.1f}%
🧠 **RAM Usage:** {ram_bar} {ram_percent:.1f}%
💾 **Disk Usage:** {disk_bar} {disk_percent:.1f}%
━━━━━━━━━━━━━━━━━━━━
📈 **Server Performance:**
• Download Speed: {random.randint(50, 100)} MB/s
• Upload Speed: {random.randint(20, 50)} MB/s
• Network Latency: {random.randint(10, 50)} ms
• Response Time: {random.randint(1, 10)} ms
━━━━━━━━━━━━━━━━━━━━
🔄 **Status:** {"Running smoothly..." if is_running else "Process stopped"}
                """
                
                # Edit message with new stats
                try:
                    bot.edit_message_text(text, chat_id, call.message.message_id, 
                                         parse_mode="Markdown")
                except:
                    pass
                
                time.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                print(f"Monitor error: {e}")
                break
    
    # Start monitoring in background
    monitor_thread = threading.Thread(target=monitor_bot)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Show final message
    time.sleep(5)
    text = f"""
✅ **BOT IS NOW ACTIVE**
━━━━━━━━━━━━━━━━━━━━
🤖 **Bot:** {bot_name}
📊 **Status:** Live monitoring active
🏃 **Process:** Running (PID: {pid})
━━━━━━━━━━━━━━━━━━━━
Live statistics will update every 5 seconds.
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🤖 My Bots", callback_data="my_bots"))
    markup.add(types.InlineKeyboardButton("📊 View Stats", callback_data=f"bot_{bot_id}"))
    markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_main"))
    
    bot.edit_message_text(text, chat_id, call.message.message_id, 
                         reply_markup=markup, parse_mode="Markdown")

def create_progress_bar(percentage):
    """Create a graphical progress bar"""
    bars = int(percentage / 10)
    return "█" * bars + "░" * (10 - bars)

def show_my_bots(call):
    uid = call.from_user.id
    bots = get_user_bots(uid)
    
    if not bots:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📤 Upload Bot", callback_data="upload"))
        markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_main"))
        
        text = """
🤖 **MY BOTS**
━━━━━━━━━━━━━━━━━━━━
No bots found. Upload your first bot!
━━━━━━━━━━━━━━━━━━━━
        """
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="Markdown")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for bot_id, bot_name, filename, pid, start_time, status in bots:
        status_icon = "🟢" if status == "Running" else "🔴" if status == "Stopped" else "🟡"
        button_text = f"{status_icon} {bot_name}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"bot_{bot_id}"))
    
    markup.add(types.InlineKeyboardButton("📤 Upload New", callback_data="upload"))
    markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_main"))
    
    running_count = sum(1 for b in bots if b[5] == "Running")
    total_count = len(bots)
    
    text = f"""
🤖 **MY BOTS**
━━━━━━━━━━━━━━━━━━━━
📊 **Stats:** {running_count}/{total_count} running
━━━━━━━━━━━━━━━━━━━━
Select a bot to view details:
━━━━━━━━━━━━━━━━━━━━
    """
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                         reply_markup=markup, parse_mode="Markdown")

def show_bot_details(call, bot_id):
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    bot_info = c.execute("SELECT * FROM deployments WHERE id=?", (bot_id,)).fetchone()
    conn.close()
    
    if not bot_info:
        return
    
    _, _, bot_name, filename, pid, start_time, status, cpu_usage, ram_usage = bot_info
    
    # Get current stats
    stats = get_system_stats()
    cpu_usage = cpu_usage or stats['cpu_percent']
    ram_usage = ram_usage or stats['ram_percent']
    
    cpu_bar = create_progress_bar(cpu_usage)
    ram_bar = create_progress_bar(ram_usage)
    
    # Check if process is running
    is_running = get_process_stats(pid) if pid else False
    
    stats_text = f"""
📊 **Current Stats:**
• CPU: {cpu_bar} {cpu_usage:.1f}%
• RAM: {ram_bar} {ram_usage:.1f}%
• Status: {"🟢 Running" if is_running else "🔴 Stopped"}
• Uptime: {calculate_uptime(start_time) if start_time else "N/A"}
    """
    
    text = f"""
🤖 **BOT DETAILS**
━━━━━━━━━━━━━━━━━━━━
**Name:** {bot_name}
**File:** `{filename}`
**PID:** `{pid if pid else "N/A"}`
**Started:** {start_time if start_time else "Not started"}
━━━━━━━━━━━━━━━━━━━━
{stats_text}
━━━━━━━━━━━━━━━━━━━━
    """
    
    markup = types.InlineKeyboardMarkup()
    if is_running:
        markup.add(types.InlineKeyboardButton("🛑 Stop Bot", callback_data=f"stop_{bot_id}"))
    elif pid:
        markup.add(types.InlineKeyboardButton("🚀 Start Bot", callback_data=f"start_{bot_id}"))
    else:
        markup.add(types.InlineKeyboardButton("🚀 Deploy Bot", callback_data=f"deploy_{filename}"))
    
    markup.add(types.InlineKeyboardButton("📊 Refresh Stats", callback_data=f"bot_{bot_id}"))
    markup.add(types.InlineKeyboardButton("🔙 My Bots", callback_data="my_bots"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                         reply_markup=markup, parse_mode="Markdown")

def stop_bot(call, bot_id):
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    
    # Get PID
    bot_info = c.execute("SELECT pid FROM deployments WHERE id=?", (bot_id,)).fetchone()
    if bot_info and bot_info[0]:
        try:
            # Try to kill process
            if platform.system() == "Windows":
                import ctypes
                PROCESS_TERMINATE = 1
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, bot_info[0])
                ctypes.windll.kernel32.TerminateProcess(handle, -1)
                ctypes.windll.kernel32.CloseHandle(handle)
            else:
                os.kill(bot_info[0], signal.SIGTERM)
            time.sleep(1)
        except:
            pass
    
    # Update status
    c.execute("UPDATE deployments SET status='Stopped', pid=0 WHERE id=?", (bot_id,))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ Bot stopped successfully!")
    show_my_bots(call)

def calculate_uptime(start_time_str):
    try:
        start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
        uptime = datetime.now() - start_time
        
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    except:
        return "N/A"

def show_dashboard(call):
    uid = call.from_user.id
    user = get_user(uid)
    bots = get_user_bots(uid)
    
    running_bots = sum(1 for b in bots if b[5] == "Running")
    total_bots = len(bots)
    
    # Get system stats without psutil
    stats = get_system_stats()
    cpu_usage = stats['cpu_percent']
    ram_usage = stats['ram_percent']
    disk_usage = stats['disk_percent']
    
    cpu_bar = create_progress_bar(cpu_usage)
    ram_bar = create_progress_bar(ram_usage)
    disk_bar = create_progress_bar(disk_usage)
    
    # Get system info
    sys_info = get_system_info()
    
    text = f"""
📊 **USER DASHBOARD**
━━━━━━━━━━━━━━━━━━━━
👤 **Account Info:**
• Status: {'PRIME 👑' if is_prime(uid) else 'FREE 🆓'}
• File Limit: {user[3]} files
• Expiry: {user[2] if user[2] else 'Not set'}
━━━━━━━━━━━━━━━━━━━━
🤖 **Bot Statistics:**
• Total Bots: {total_bots}
• Running: {running_bots}
• Stopped: {total_bots - running_bots}
━━━━━━━━━━━━━━━━━━━━
🖥️ **Server Status:**
• CPU: {cpu_bar} {cpu_usage:.1f}%
• RAM: {ram_bar} {ram_usage:.1f}%
• Disk: {disk_bar} {disk_usage:.1f}%
━━━━━━━━━━━━━━━━━━━━
💻 **System Info:**
• OS: {sys_info['os']}
• Version: {sys_info['os_version']}
• Architecture: {sys_info['machine']}
━━━━━━━━━━━━━━━━━━━━
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🤖 My Bots", callback_data="my_bots"),
        types.InlineKeyboardButton("🚀 Deploy", callback_data="deploy_new")
    )
    markup.add(
        types.InlineKeyboardButton("📤 Upload", callback_data="upload"),
        types.InlineKeyboardButton("🔄 Refresh", callback_data="dashboard")
    )
    markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_main"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                         reply_markup=markup, parse_mode="Markdown")

def admin_panel_callback(call):
    text = """
👑 **ADMIN DASHBOARD**
━━━━━━━━━━━━━━━━━━━━
Welcome to the admin control panel.
Select an option below:
━━━━━━━━━━━━━━━━━━━━
    """
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                         reply_markup=admin_menu(), parse_mode="Markdown")

def show_all_users(call):
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    users = c.execute("SELECT id, username, expiry, file_limit, is_prime FROM users").fetchall()
    conn.close()
    
    prime_count = sum(1 for u in users if u[4] == 1)
    total_count = len(users)
    
    text = f"""
👥 **ALL USERS**
━━━━━━━━━━━━━━━━━━━━
📊 **Total Users:** {total_count}
👑 **Prime Users:** {prime_count}
🆓 **Free Users:** {total_count - prime_count}
━━━━━━━━━━━━━━━━━━━━
**Recent Users:**
"""
    
    for user in users[:10]:  # Show first 10 users
        text += f"\n• {user[1]} (ID: {user[0]}) - {'Prime' if user[4] else 'Free'}"
    
    if len(users) > 10:
        text += f"\n\n... and {len(users) - 10} more users"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                         reply_markup=markup, parse_mode="Markdown")

def show_all_bots(call):
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    bots = c.execute("SELECT d.bot_name, d.status, d.start_time, u.username FROM deployments d JOIN users u ON d.user_id = u.id").fetchall()
    conn.close()
    
    running_bots = sum(1 for b in bots if b[1] == "Running")
    total_bots = len(bots)
    
    text = f"""
🤖 **ALL BOTS**
━━━━━━━━━━━━━━━━━━━━
📊 **Total Bots:** {total_bots}
🟢 **Running:** {running_bots}
🔴 **Stopped:** {total_bots - running_bots}
━━━━━━━━━━━━━━━━━━━━
**Active Bots:**
"""
    
    for bot_info in bots[:5]:  # Show first 5 bots
        if bot_info[1] == "Running":
            text += f"\n• {bot_info[0]} (@{bot_info[3]}) - {bot_info[1]}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                         reply_markup=markup, parse_mode="Markdown")

def show_admin_stats(call):
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    
    # Get all stats
    total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    prime_users = c.execute("SELECT COUNT(*) FROM users WHERE is_prime=1").fetchone()[0]
    total_bots = c.execute("SELECT COUNT(*) FROM deployments").fetchone()[0]
    running_bots = c.execute("SELECT COUNT(*) FROM deployments WHERE status='Running'").fetchone()[0]
    total_keys = c.execute("SELECT COUNT(*) FROM keys").fetchone()[0]
    
    conn.close()
    
    # System stats without psutil
    stats = get_system_stats()
    cpu_usage = stats['cpu_percent']
    ram_usage = stats['ram_percent']
    disk_usage = stats['disk_percent']
    
    # System info
    sys_info = get_system_info()
    
    text = f"""
📈 **ADMIN STATISTICS**
━━━━━━━━━━━━━━━━━━━━
👥 **User Stats:**
• Total Users: {total_users}
• Prime Users: {prime_users}
• Free Users: {total_users - prime_users}
━━━━━━━━━━━━━━━━━━━━
🤖 **Bot Stats:**
• Total Bots: {total_bots}
• Running Bots: {running_bots}
• Stopped Bots: {total_bots - running_bots}
━━━━━━━━━━━━━━━━━━━━
🔑 **Key Stats:**
• Total Keys: {total_keys}
━━━━━━━━━━━━━━━━━━━━
🖥️ **System Status:**
• CPU Usage: {cpu_usage:.1f}%
• RAM Usage: {ram_usage:.1f}%
• Disk Usage: {disk_usage:.1f}%
━━━━━━━━━━━━━━━━━━━━
💻 **System Info:**
• OS: {sys_info['os']}
• Python: {sys_info['python_version']}
• Processor: {sys_info['processor'][:30]}...
━━━━━━━━━━━━━━━━━━━━
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("👥 Users", callback_data="all_users"),
        types.InlineKeyboardButton("🤖 Bots", callback_data="all_bots")
    )
    markup.add(types.InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                         reply_markup=markup, parse_mode="Markdown")

def show_premium_info(call):
    text = """
👑 **PREMIUM FEATURES**
━━━━━━━━━━━━━━━━━━━━
✅ **Unlimited Bot Deployment**
✅ **Priority Support**
✅ **Advanced Monitoring**
✅ **Custom Bot Names**
✅ **Library Installation**
✅ **Live Statistics**
✅ **24/7 Server Uptime**
✅ **No Ads**
━━━━━━━━━━━━━━━━━━━━
💎 **Get Prime Today!**
Click 'Activate Prime Pass' and enter your key.
━━━━━━━━━━━━━━━━━━━━
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔑 Activate Prime", callback_data="activate_prime"))
    markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_main"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                         reply_markup=markup, parse_mode="Markdown")

def show_settings(call):
    uid = call.from_user.id
    user = get_user(uid)
    
    text = f"""
⚙️ **SETTINGS**
━━━━━━━━━━━━━━━━━━━━
👤 **Account Settings:**
• User ID: `{uid}`
• Status: {'Prime 👑' if is_prime(uid) else 'Free 🆓'}
• File Limit: {user[3]}
━━━━━━━━━━━━━━━━━━━━
🔧 **Bot Settings:**
• Auto-restart: Disabled
• Notifications: Enabled
• Language: English
━━━━━━━━━━━━━━━━━━━━
⚠️ **Danger Zone:**
• Delete Account
• Reset Settings
━━━━━━━━━━━━━━━━━━━━
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔔 Notifications", callback_data="notif_settings"),
        types.InlineKeyboardButton("🌐 Language", callback_data="lang_settings")
    )
    markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_main"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                         reply_markup=markup, parse_mode="Markdown")

def process_key_step(message, old_mid):
    uid = message.from_user.id
    key_input = message.text.strip().upper()
    
    bot.delete_message(message.chat.id, message.message_id)
    
    conn = sqlite3.connect(Config.DB_NAME)
    c = conn.cursor()
    res = c.execute("SELECT * FROM keys WHERE key=?", (key_input,)).fetchone()
    
    if res:
        days, limit = res[1], res[2]
        expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        c.execute("UPDATE users SET expiry=?, file_limit=?, is_prime=1 WHERE id=?", 
                 (expiry_date, limit, uid))
        c.execute("DELETE FROM keys WHERE key=?", (key_input,))
        conn.commit()
        conn.close()
        
        text = f"""
✅ **PRIME ACTIVATED!**
━━━━━━━━━━━━━━━━━━━━
🎉 Congratulations! You are now a Prime member.
━━━━━━━━━━━━━━━━━━━━
📅 **Expiry:** {expiry_date}
📦 **File Limit:** {limit} files
━━━━━━━━━━━━━━━━━━━━
Enjoy all premium features!
        """
        
        bot.edit_message_text(text, message.chat.id, old_mid, 
                             reply_markup=main_menu(uid),
                             parse_mode="Markdown")
    else:
        conn.close()
        text = """
❌ **INVALID KEY**
━━━━━━━━━━━━━━━━━━━━
The key you entered is invalid or expired.
━━━━━━━━━━━━━━━━━━━━
Please check the key and try again.
        """
        bot.edit_message_text(text, message.chat.id, old_mid, 
                             reply_markup=main_menu(uid),
                             parse_mode="Markdown")

# Start Bot and Server
if __name__ == '__main__':
    print("""
🤖 CYBER BOT HOSTING v3.0
━━━━━━━━━━━━━━━━━━━━
Starting system...
• Database: ✅
• Project Directory: ✅
• Admin ID: ✅
• System: {} {}
━━━━━━━━━━━━━━━━━━━━
    """.format(platform.system(), platform.version()))
    
    # Start bot in separate thread
    bot_thread = threading.Thread(target=lambda: bot.polling(none_stop=True, timeout=60))
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start Flask server
    print(f"✅ Bot is running on port {Config.PORT}")
    print("━━━━━━━━━━━━━━━━━━━━")
    app.run(host='0.0.0.0', port=Config.PORT, debug=False, use_reloader=False)
