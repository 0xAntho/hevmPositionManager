import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Forcer l'utilisation du token de test
os.environ['TELEGRAM_BOT_TOKEN'] = os.getenv('TELEGRAM_BOT_TOKEN_TEST')

# Importer et lancer le bot
from TelegramManager import TelegramLPBot

if __name__ == "__main__":
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN_TEST')
    RPC_URL = os.getenv('RPC_URL')
    WALLET_ADDRESS = os.getenv('WALLET_ADDRESS')
    CHAIN_ID = int(os.getenv('CHAIN_ID', '999'))

    if not TELEGRAM_TOKEN:
        print("❌ Erreur: TELEGRAM_BOT_TOKEN_TEST non défini dans .env")
        exit(1)

    print("🧪 Mode TEST - Utilisation du bot de test")
    print(f"Token: {TELEGRAM_TOKEN[:10]}...")

    bot = TelegramLPBot(TELEGRAM_TOKEN, RPC_URL, WALLET_ADDRESS, CHAIN_ID)
    bot.run()