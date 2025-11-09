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
    MONITOR_INTERVAL = int(os.getenv('MONITOR_INTERVAL_MINUTES', '60'))

    # Parse admin IDs
    admin_ids_str = os.getenv('ADMIN_USER_IDS', '')
    ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip().isdigit()]

    if not TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN_TEST not defined in .env")
        exit(1)
    if not RPC_URL:
        print("❌ Error: RPC_URL not defined in .env")
        exit(1)

    print("🧪 TEST Mode - Using test bot")

    # Pass ALL parameters including MONITOR_INTERVAL
    bot = TelegramLPBot(TELEGRAM_TOKEN, RPC_URL, CHAIN_ID, ADMIN_IDS, MONITOR_INTERVAL)
    bot.run()