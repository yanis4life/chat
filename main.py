import telebot
import os
import sys
import subprocess
import zipfile
import shutil
import importlib
import time
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "8924085297:AAF0ik7vvXG7qMfw93cy1Zfo6aH9Gd0RtKI"
ALLOWED_USERS = [7125289523]  # Your user ID

# Use home directory instead of /root
HOME_DIR = os.path.expanduser("~/www")
TEMP_DIR = os.path.join(HOME_DIR, "temp_executions")

try:
    bot = telebot.TeleBot(BOT_TOKEN)
    bot_info = bot.get_me()
    print(f"✅ Bot connected: @{bot_info.username}")
except Exception as e:
    print(f"❌ Token error: {e}")
    sys.exit(1)

class PyExecutor:
    def __init__(self):
        self.temp_dir = TEMP_DIR
        try:
            os.makedirs(self.temp_dir, exist_ok=True)
            print(f"✅ Temp directory created: {self.temp_dir}")
        except Exception as e:
            print(f"❌ Cannot create temp dir: {e}")
            # Fallback to /tmp
            self.temp_dir = "/tmp/py_executor"
            os.makedirs(self.temp_dir, exist_ok=True)
            print(f"✅ Using fallback temp dir: {self.temp_dir}")
    
    def install_modules_from_code(self, code):
        installed = []
        import_lines = []
        
        for line in code.split('\n'):
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                import_lines.append(line)
        
        for line in import_lines:
            try:
                if line.startswith('import '):
                    module = line.split('import ')[1].split()[0].split('.')[0]
                elif line.startswith('from '):
                    module = line.split('from ')[1].split()[0].split('.')[0]
                else:
                    continue
                
                try:
                    importlib.import_module(module)
                except ImportError:
                    logger.info(f"Installing: {module}")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", module])
                    installed.append(module)
            except:
                continue
        
        return installed
    
    def install_modules_from_requirements(self, req_file):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "-r", req_file])
            return True
        except Exception as e:
            logger.error(f"Requirements error: {e}")
            return False
    
    def execute_python_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                code = f.read()
            
            installed = self.install_modules_from_code(code)
            
            # Execute from the file's directory
            work_dir = os.path.dirname(file_path)
            process = subprocess.Popen(
                [sys.executable, file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=work_dir
            )
            
            stdout, stderr = process.communicate()
            
            result = ""
            if installed:
                result += f"📦 Installed: {', '.join(installed)}\n\n"
            if stdout:
                result += f"📤 Output:\n{stdout}\n"
            if stderr:
                result += f"⚠️ Errors:\n{stderr}\n"
            
            return result if result else "✅ Done (no output)"
            
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def extract_zip(self, zip_path, extract_to):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            
            # List extracted files for debugging
            extracted_files = []
            for root, dirs, files in os.walk(extract_to):
                for file in files:
                    extracted_files.append(os.path.join(root, file))
            
            logger.info(f"Extracted {len(extracted_files)} files")
            return True
        except Exception as e:
            logger.error(f"ZIP error: {e}")
            return False
    
    def find_main_py(self, directory):
        """Find the main Python file"""
        priority_files = ['main.py', 'app.py', 'bot.py', 'run.py']
        
        # First check root of extracted directory
        for file in priority_files:
            file_path = os.path.join(directory, file)
            if os.path.exists(file_path):
                logger.info(f"Found main file: {file_path}")
                return file_path
        
        # Then check one level deep
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                for file in priority_files:
                    file_path = os.path.join(item_path, file)
                    if os.path.exists(file_path):
                        logger.info(f"Found main file: {file_path}")
                        return file_path
        
        # Any .py file in root
        for file in os.listdir(directory):
            if file.endswith('.py'):
                file_path = os.path.join(directory, file)
                logger.info(f"Found Python file: {file_path}")
                return file_path
        
        # Any .py file one level deep
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                for file in os.listdir(item_path):
                    if file.endswith('.py'):
                        file_path = os.path.join(item_path, file)
                        logger.info(f"Found Python file: {file_path}")
                        return file_path
        
        logger.error(f"No Python file found in {directory}")
        return None
    
    def cleanup(self, path):
        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

executor = PyExecutor()

def is_authorized(user_id):
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_authorized(message.from_user.id):
        bot.reply_to(message, "❌ Unauthorized")
        return
    
    welcome_text = """
🚀 *Python Executor Bot*

Send `.py` file - Execute Python script
Send `.zip` file - Extract & run project

✨ *Features:*
• No time limits
• Auto-install modules
• ZIP support
• requirements.txt support

/run `code` - Execute code directly
    """
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if not is_authorized(message.from_user.id):
        bot.reply_to(message, "❌ Unauthorized")
        return
    
    try:
        file_name = message.document.file_name
        file_size = message.document.file_size
        
        # Send initial status
        status_msg = bot.reply_to(message, f"📥 Downloading {file_name}...")
        
        # Get file info and download
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Create unique temp directory
        temp_id = f"{message.from_user.id}_{int(time.time())}"
        user_temp_dir = os.path.join(executor.temp_dir, temp_id)
        os.makedirs(user_temp_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(user_temp_dir, file_name)
        with open(file_path, 'wb') as f:
            f.write(downloaded_file)
        
        logger.info(f"File saved: {file_path} ({file_size} bytes)")
        
        if file_name.endswith('.zip'):
            # Update status
            bot.edit_message_text("📦 Extracting ZIP...", message.chat.id, status_msg.message_id)
            
            extract_dir = os.path.join(user_temp_dir, 'extracted')
            os.makedirs(extract_dir, exist_ok=True)
            
            if executor.extract_zip(file_path, extract_dir):
                # Check for requirements.txt
                req_file = None
                for root, dirs, files in os.walk(extract_dir):
                    if 'requirements.txt' in files:
                        req_file = os.path.join(root, 'requirements.txt')
                        break
                
                if req_file:
                    bot.edit_message_text("📦 Installing dependencies...", message.chat.id, status_msg.message_id)
                    executor.install_modules_from_requirements(req_file)
                
                # Find main file
                main_file = executor.find_main_py(extract_dir)
                
                if main_file:
                    bot.edit_message_text(f"⚡ Running: {os.path.basename(main_file)}", message.chat.id, status_msg.message_id)
                    
                    result = executor.execute_python_file(main_file)
                    
                    # Delete status message
                    bot.delete_message(message.chat.id, status_msg.message_id)
                    
                    # Send result
                    if len(result) > 4000:
                        for i in range(0, len(result), 4000):
                            chunk = result[i:i+4000]
                            bot.send_message(message.chat.id, f"```\n{chunk}\n```", parse_mode='Markdown')
                    else:
                        bot.reply_to(message, f"```\n{result}\n```", parse_mode='Markdown')
                else:
                    bot.edit_message_text("❌ No Python file found in ZIP", message.chat.id, status_msg.message_id)
            else:
                bot.edit_message_text("❌ Failed to extract ZIP", message.chat.id, status_msg.message_id)
        
        elif file_name.endswith('.py'):
            # Update status
            bot.edit_message_text(f"⚡ Running: {file_name}", message.chat.id, status_msg.message_id)
            
            result = executor.execute_python_file(file_path)
            
            # Delete status message
            bot.delete_message(message.chat.id, status_msg.message_id)
            
            # Send result
            if len(result) > 4000:
                for i in range(0, len(result), 4000):
                    chunk = result[i:i+4000]
                    bot.send_message(message.chat.id, f"```\n{chunk}\n```", parse_mode='Markdown')
            else:
                bot.reply_to(message, f"```\n{result}\n```", parse_mode='Markdown')
        
        else:
            bot.edit_message_text(f"❌ Unsupported file: {file_name}\nSend .py or .zip only", message.chat.id, status_msg.message_id)
        
        # Cleanup
        executor.cleanup(user_temp_dir)
        
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        try:
            bot.reply_to(message, f"❌ Error: {str(e)}")
        except:
            pass

@bot.message_handler(commands=['run'])
def run_command(message):
    if not is_authorized(message.from_user.id):
        bot.reply_to(message, "❌ Unauthorized")
        return
    
    try:
        code = message.text.split('/run', 1)[1].strip()
        
        if not code:
            bot.reply_to(message, "❌ Usage: /run print('Hello')")
            return
        
        temp_id = f"{message.from_user.id}_{int(time.time())}"
        user_temp_dir = os.path.join(executor.temp_dir, temp_id)
        os.makedirs(user_temp_dir, exist_ok=True)
        
        file_path = os.path.join(user_temp_dir, 'script.py')
        with open(file_path, 'w') as f:
            f.write(code)
        
        processing_msg = bot.reply_to(message, "⚡ Executing...")
        result = executor.execute_python_file(file_path)
        
        bot.delete_message(message.chat.id, processing_msg.message_id)
        
        if len(result) > 4000:
            for i in range(0, len(result), 4000):
                chunk = result[i:i+4000]
                bot.send_message(message.chat.id, f"```\n{chunk}\n```", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"```\n{result}\n```", parse_mode='Markdown')
        
        executor.cleanup(user_temp_dir)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    if not is_authorized(message.from_user.id):
        return
    
    if not message.document:
        bot.reply_to(message, "Send .py or .zip file, or use /run command")

if __name__ == '__main__':
    print("🤖 Bot starting...")
    print(f"📁 Home directory: {HOME_DIR}")
    print(f"📁 Temp directory: {TEMP_DIR}")
    print(f"✅ Authorized users: {ALLOWED_USERS}")
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(15)