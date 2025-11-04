import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from web3 import Web3
import asyncio
from typing import List, Dict, Optional
import time

# Charger les variables d'environnement
load_dotenv()

# Importer votre classe (assurez-vous que PoolManager.py est dans le même dossier)
from PoolManager import LiquidityPoolTracker

# États de la conversation
WAITING_ADDRESS = 1


class TelegramLPBot:
    def __init__(self, token: str, rpc_url: str, chain_id: int = 999):
        self.token = token
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.tracker = LiquidityPoolTracker(rpc_url, chain_id, delay_between_calls=1.0)
        # Dictionnaire pour stocker les adresses des utilisateurs
        self.user_addresses = {}

    def get_main_keyboard(self):
        """Retourne le clavier permanent du menu principal"""
        keyboard = [
            [KeyboardButton("📊 Mes Positions"), KeyboardButton("🔄 Rafraîchir")],
            [KeyboardButton("⚠️ Alertes"), KeyboardButton("🔄 Changer Wallet")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start - Demande l'adresse du wallet"""
        user_id = update.effective_user.id

        # Vérifier si l'utilisateur a déjà une adresse
        if user_id in self.user_addresses:
            welcome_msg = (
                f"👋 Bon retour !\n\n"
                f"📍 Wallet actuel:\n`{self.user_addresses[user_id]}`\n\n"
                f"Utilisez les boutons ci-dessous ou envoyez `/wallet` pour changer d'adresse."
            )
            await update.message.reply_text(
                welcome_msg,
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )
            return ConversationHandler.END

        # Nouveau utilisateur
        welcome_msg = (
            f"🤖 *Bienvenue sur le LP Position Tracker!*\n\n"
            f"🔗 Chain: Hyperliquid EVM (ID: {self.chain_id})\n\n"
            f"Pour commencer, envoyez-moi l'adresse du wallet que vous souhaitez surveiller.\n\n"
            f"📝 Format: `0x...`"
        )
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
        return WAITING_ADDRESS

    async def receive_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reçoit et valide l'adresse du wallet"""
        user_id = update.effective_user.id
        address = update.message.text.strip()

        # Valider l'adresse
        if not Web3.is_address(address):
            await update.message.reply_text(
                "❌ Adresse invalide. Veuillez envoyer une adresse Ethereum valide commençant par 0x"
            )
            return WAITING_ADDRESS

        # Normaliser l'adresse
        address = Web3.to_checksum_address(address)

        # Sauvegarder l'adresse pour cet utilisateur
        self.user_addresses[user_id] = address

        success_msg = (
            f"✅ *Wallet configuré avec succès!*\n\n"
            f"📍 Adresse:\n`{address}`\n\n"
            f"Utilisez les boutons ci-dessous pour interagir:"
        )

        await update.message.reply_text(
            success_msg,
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
        )

        return ConversationHandler.END

    async def change_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Permet de changer l'adresse du wallet"""
        user_id = update.effective_user.id

        if user_id in self.user_addresses:
            current_msg = f"📍 Wallet actuel:\n`{self.user_addresses[user_id]}`\n\n"
        else:
            current_msg = ""

        msg = (
            f"{current_msg}"
            f"Envoyez la nouvelle adresse du wallet que vous souhaitez surveiller.\n\n"
            f"📝 Format: `0x...`"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return WAITING_ADDRESS

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Annule la conversation"""
        await update.message.reply_text(
            "❌ Opération annulée. Utilisez /start pour recommencer."
        )
        return ConversationHandler.END

    def get_user_address(self, user_id: int) -> Optional[str]:
        """Récupère l'adresse d'un utilisateur"""
        return self.user_addresses.get(user_id)

    async def view_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Affiche toutes les positions"""
        user_id = update.effective_user.id
        wallet_address = self.get_user_address(user_id)

        if not wallet_address:
            await update.message.reply_text(
                "❌ Vous devez d'abord configurer une adresse avec /start"
            )
            return

        # Gérer à la fois les callback queries et les messages texte
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            message = query.message
        else:
            message = update.message

        # Message de chargement
        loading_msg = await message.reply_text("⏳ Récupération des positions...")

        try:
            # Récupérer les positions
            positions = await asyncio.to_thread(
                self.tracker.get_positions,
                wallet_address,
                include_pool_info=True
            )

            if not positions:
                await loading_msg.edit_text("❌ Aucune position active trouvée.")
                return

            # Afficher chaque position
            for i, position in enumerate(positions):
                msg = self._format_position(position)

                # Bouton pour voir les détails
                keyboard = [[
                    InlineKeyboardButton("🔍 Détails complets", callback_data=f'details_{position["token_id"]}')
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await message.reply_text(
                    msg,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )

            await loading_msg.delete()

            # Message de résumé
            summary = f"✅ *{len(positions)} position(s) active(s) trouvée(s)*"
            await message.reply_text(summary, parse_mode='Markdown')

        except Exception as e:
            await loading_msg.edit_text(f"❌ Erreur: {str(e)}")

    async def out_of_range_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Affiche uniquement les positions hors range"""
        user_id = update.effective_user.id
        wallet_address = self.get_user_address(user_id)

        if not wallet_address:
            await update.message.reply_text(
                "❌ Vous devez d'abord configurer une adresse avec /start"
            )
            return

        # Gérer à la fois les callback queries et les messages texte
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            message = query.message
        else:
            message = update.message

        loading_msg = await message.reply_text("⏳ Vérification des positions...")

        try:
            positions = await asyncio.to_thread(
                self.tracker.get_positions,
                wallet_address,
                include_pool_info=True
            )

            # Filtrer les positions hors range
            out_of_range = []
            for position in positions:
                if position.get('pool_address'):
                    pool_info = self.tracker.get_pool_current_tick(position['pool_address'])
                    if pool_info:
                        current_tick = pool_info['current_tick']
                        if not (position['tick_lower'] <= current_tick <= position['tick_upper']):
                            position['current_tick'] = current_tick
                            out_of_range.append(position)

            await loading_msg.delete()

            if not out_of_range:
                await message.reply_text("✅ Toutes vos positions sont IN RANGE! 🎉")
                return

            # Afficher les positions hors range
            alert_msg = f"⚠️ *ALERTE: {len(out_of_range)} position(s) OUT OF RANGE*\n\n"
            await message.reply_text(alert_msg, parse_mode='Markdown')

            for position in out_of_range:
                msg = self._format_position(position, alert_mode=True)
                await message.reply_text(msg, parse_mode='Markdown')

        except Exception as e:
            await loading_msg.edit_text(f"❌ Erreur: {str(e)}")

    def _format_position(self, position: Dict, alert_mode: bool = False) -> str:
        """Formate une position pour l'affichage Telegram"""
        token0_sym = position.get('token0_symbol', 'Token0')
        token1_sym = position.get('token1_symbol', 'Token1')

        # En-tête
        if alert_mode:
            header = f"🚨 *Position #{position['token_id']}* - OUT OF RANGE\n"
        else:
            header = f"💼 *Position #{position['token_id']}*\n"

        msg = header
        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"📌 Pair: *{token0_sym}/{token1_sym}*\n"
        msg += f"💰 Fee: {position['fee'] / 10000}%\n\n"

        # Range
        msg += f"📊 *Range de liquidité:*\n"
        msg += f"  Lower: {position['tick_lower']} (${position['price_lower']:.6f})\n"
        msg += f"  Upper: {position['tick_upper']} (${position['price_upper']:.6f})\n\n"

        # État du pool si disponible
        if position.get('pool_address'):
            pool_info = self.tracker.get_pool_current_tick(position['pool_address'])
            if pool_info:
                current_tick = pool_info['current_tick']
                in_range = position['tick_lower'] <= current_tick <= position['tick_upper']

                msg += f"🎯 *État actuel:*\n"
                msg += f"  Tick: {current_tick}\n"
                msg += f"  Prix: ${pool_info['price']:.6f}\n"

                if in_range:
                    msg += f"  Status: ✅ IN RANGE\n\n"
                else:
                    msg += f"  Status: ⚠️ OUT OF RANGE\n"
                    if current_tick < position['tick_lower']:
                        msg += f"  → Prix en dessous (100% {token0_sym})\n\n"
                    else:
                        msg += f"  → Prix au dessus (100% {token1_sym})\n\n"

                # Montants de tokens
                if 'token0_decimals' in position and 'token1_decimals' in position:
                    amounts = self.tracker.calculate_token_amounts(
                        position['liquidity'],
                        pool_info['sqrt_price_x96'],
                        position['tick_lower'],
                        position['tick_upper'],
                        current_tick,
                        position['token0_decimals'],
                        position['token1_decimals']
                    )

                    msg += f"💵 *Composition:*\n"
                    msg += f"  {token0_sym}: {amounts['amount0']:.6f} ({amounts['percentage0']:.1f}%)\n"
                    msg += f"  {token1_sym}: {amounts['amount1']:.6f} ({amounts['percentage1']:.1f}%)\n"

        return msg

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Affiche les informations du wallet"""
        user_id = update.effective_user.id
        wallet_address = self.get_user_address(user_id)

        if not wallet_address:
            await update.message.reply_text(
                "❌ Vous devez d'abord configurer une adresse avec /start"
            )
            return

        info_msg = (
            f"ℹ️ *Informations*\n\n"
            f"📍 *Wallet surveillé:*\n`{wallet_address}`\n\n"
            f"🔗 *Chain:* Hyperliquid EVM (ID: {self.chain_id})\n"
            f"🏭 *Position Manager:*\n`{self.tracker.position_managers[self.chain_id]}`\n"
            f"🏭 *Factory:*\n`{self.tracker.factories[self.chain_id]}`\n\n"
            f"💡 *Commandes disponibles:*\n"
            f"/start - Configuration initiale\n"
            f"/wallet - Changer de wallet\n"
            f"/positions - Voir toutes les positions\n"
            f"/alerts - Positions hors range uniquement\n"
            f"/info - Afficher ces informations"
        )
        await update.message.reply_text(info_msg, parse_mode='Markdown')

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gère les messages texte du clavier permanent"""
        user_id = update.effective_user.id

        # Vérifier si l'utilisateur a une adresse configurée
        if user_id not in self.user_addresses:
            await update.message.reply_text(
                "❌ Vous devez d'abord configurer une adresse avec /start"
            )
            return

        text = update.message.text

        if text == "📊 Mes Positions":
            await self.view_positions(update, context)
        elif text == "🔄 Rafraîchir":
            await self.view_positions(update, context)
        elif text == "⚠️ Alertes":
            await self.out_of_range_positions(update, context)
        elif text == "🔄 Changer Wallet":
            return await self.change_wallet(update, context)
        else:
            await update.message.reply_text(
                "Utilisez les boutons du menu ou une commande comme /start",
                reply_markup=self.get_main_keyboard()
            )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gère les clics sur les boutons inline"""
        query = update.callback_query

        if query.data == 'view_positions':
            await self.view_positions(update, context)
        elif query.data == 'refresh':
            await self.view_positions(update, context)
        elif query.data == 'out_of_range':
            await self.out_of_range_positions(update, context)
        elif query.data.startswith('details_'):
            # TODO: Implémenter l'affichage détaillé d'une position
            await query.answer("Fonctionnalité à venir!")

    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /positions - raccourci pour voir les positions"""
        await self.view_positions(update, context)

    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /alerts - raccourci pour les positions hors range"""
        await self.out_of_range_positions(update, context)

    def run(self):
        """Lance le bot"""
        application = Application.builder().token(self.token).build()

        # Conversation handler pour la configuration du wallet
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                CommandHandler("wallet", self.change_wallet)
            ],
            states={
                WAITING_ADDRESS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_address)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )

        # Handlers
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("positions", self.positions_command))
        application.add_handler(CommandHandler("alerts", self.alerts_command))
        application.add_handler(CommandHandler("info", self.info_command))
        application.add_handler(CallbackQueryHandler(self.button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

        # Lancer le bot
        print("🤖 Bot Telegram démarré!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # Charger la configuration
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    RPC_URL = os.getenv('RPC_URL')
    CHAIN_ID = int(os.getenv('CHAIN_ID', '999'))

    # Vérifier la configuration
    if not TELEGRAM_TOKEN:
        print("❌ Erreur: TELEGRAM_BOT_TOKEN non défini dans .env")
        exit(1)
    if not RPC_URL:
        print("❌ Erreur: RPC_URL non défini dans .env")
        exit(1)

    # Créer et lancer le bot (sans wallet_address par défaut)
    bot = TelegramLPBot(TELEGRAM_TOKEN, RPC_URL, CHAIN_ID)
    bot.run()