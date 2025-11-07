import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Force test bot token
os.environ['TELEGRAM_BOT_TOKEN'] = os.getenv('TELEGRAM_BOT_TOKEN_TEST')

# Import bot
from telegram_bot import TelegramLPBot

if __name__ == "__main__":
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN_TEST')
    RPC_URL = os.getenv('RPC_URL')
    CHAIN_ID = int(os.getenv('CHAIN_ID', '999'))

    # Parse admin IDs (AJOUT ICI !)
    admin_ids_str = os.getenv('ADMIN_USER_IDS', '')
    ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip().isdigit()]

    if not TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN_TEST not defined in .env")
        exit(1)

    print("🧪 TEST Mode - Using test bot")
    print(f"Token: {TELEGRAM_TOKEN[:10]}...")

    # Pass ADMIN_IDS here!
    bot = TelegramLPBot(TELEGRAM_TOKEN, RPC_URL, CHAIN_ID, ADMIN_IDS)
    bot.run()