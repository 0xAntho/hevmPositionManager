import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from web3 import Web3
import asyncio
from typing import List, Dict, Optional
import time

# Charger les variables d'environnement
load_dotenv()

# Importer votre classe (assurez-vous que PoolManager.py est dans le même dossier)
from PoolManager import LiquidityPoolTracker


class TelegramLPBot:
    def __init__(self, token: str, rpc_url: str, wallet_address: str, chain_id: int = 999):
        self.token = token
        self.rpc_url = rpc_url
        self.wallet_address = wallet_address
        self.chain_id = chain_id
        self.tracker = LiquidityPoolTracker(rpc_url, chain_id, delay_between_calls=1.0)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        keyboard = [
            [InlineKeyboardButton("📊 Voir mes positions", callback_data='view_positions')],
            [InlineKeyboardButton("🔄 Rafraîchir", callback_data='refresh')],
            [InlineKeyboardButton("⚠️ Positions hors range", callback_data='out_of_range')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_msg = (
            f"🤖 *Bienvenue sur le LP Position Tracker!*\n\n"
            f"📍 Wallet surveillé:\n`{self.wallet_address}`\n\n"
            f"🔗 Chain ID: {self.chain_id}\n"
            f"🏭 Position Manager: `{self.tracker.position_managers[self.chain_id]}`\n\n"
            f"Utilisez les boutons ci-dessous pour interagir:"
        )

        await update.message.reply_text(
            welcome_msg,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def view_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Affiche toutes les positions"""
        query = update.callback_query
        await query.answer()

        # Message de chargement
        loading_msg = await query.message.reply_text("⏳ Récupération des positions...")

        try:
            # Récupérer les positions
            positions = await asyncio.to_thread(
                self.tracker.get_positions,
                self.wallet_address,
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

                await query.message.reply_text(
                    msg,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )

            await loading_msg.delete()

            # Message de résumé
            summary = f"✅ *{len(positions)} position(s) active(s) trouvée(s)*"
            await query.message.reply_text(summary, parse_mode='Markdown')

        except Exception as e:
            await loading_msg.edit_text(f"❌ Erreur: {str(e)}")

    async def out_of_range_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Affiche uniquement les positions hors range"""
        query = update.callback_query
        await query.answer()

        loading_msg = await query.message.reply_text("⏳ Vérification des positions...")

        try:
            positions = await asyncio.to_thread(
                self.tracker.get_positions,
                self.wallet_address,
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
                await query.message.reply_text("✅ Toutes vos positions sont IN RANGE! 🎉")
                return

            # Afficher les positions hors range
            alert_msg = f"⚠️ *ALERTE: {len(out_of_range)} position(s) OUT OF RANGE*\n\n"
            await query.message.reply_text(alert_msg, parse_mode='Markdown')

            for position in out_of_range:
                msg = self._format_position(position, alert_mode=True)
                await query.message.reply_text(msg, parse_mode='Markdown')

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

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gère les clics sur les boutons"""
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
        # Simuler un callback query
        await update.message.reply_text("⏳ Récupération des positions...")

        try:
            positions = await asyncio.to_thread(
                self.tracker.get_positions,
                self.wallet_address,
                include_pool_info=True
            )

            if not positions:
                await update.message.reply_text("❌ Aucune position active trouvée.")
                return

            for position in positions:
                msg = self._format_position(position)
                await update.message.reply_text(msg, parse_mode='Markdown')

            summary = f"✅ *{len(positions)} position(s) active(s)*"
            await update.message.reply_text(summary, parse_mode='Markdown')

        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {str(e)}")

    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /alerts - raccourci pour les positions hors range"""
        await update.message.reply_text("⏳ Vérification des positions...")

        try:
            positions = await asyncio.to_thread(
                self.tracker.get_positions,
                self.wallet_address,
                include_pool_info=True
            )

            out_of_range = []
            for position in positions:
                if position.get('pool_address'):
                    pool_info = self.tracker.get_pool_current_tick(position['pool_address'])
                    if pool_info:
                        current_tick = pool_info['current_tick']
                        if not (position['tick_lower'] <= current_tick <= position['tick_upper']):
                            out_of_range.append(position)

            if not out_of_range:
                await update.message.reply_text("✅ Toutes vos positions sont IN RANGE! 🎉")
                return

            alert_msg = f"⚠️ *{len(out_of_range)} position(s) OUT OF RANGE*\n\n"
            await update.message.reply_text(alert_msg, parse_mode='Markdown')

            for position in out_of_range:
                msg = self._format_position(position, alert_mode=True)
                await update.message.reply_text(msg, parse_mode='Markdown')

        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {str(e)}")

    def run(self):
        """Lance le bot"""
        application = Application.builder().token(self.token).build()

        # Handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("positions", self.positions_command))
        application.add_handler(CommandHandler("alerts", self.alerts_command))
        application.add_handler(CallbackQueryHandler(self.button_handler))

        # Lancer le bot
        print("🤖 Bot Telegram démarré!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # Charger la configuration
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    RPC_URL = os.getenv('RPC_URL')
    WALLET_ADDRESS = os.getenv('WALLET_ADDRESS')
    CHAIN_ID = int(os.getenv('CHAIN_ID', '999'))

    # Vérifier la configuration
    if not TELEGRAM_TOKEN:
        print("❌ Erreur: TELEGRAM_BOT_TOKEN non défini dans .env")
        exit(1)
    if not RPC_URL:
        print("❌ Erreur: RPC_URL non défini dans .env")
        exit(1)
    if not WALLET_ADDRESS:
        print("❌ Erreur: WALLET_ADDRESS non défini dans .env")
        exit(1)

    # Créer et lancer le bot
    bot = TelegramLPBot(TELEGRAM_TOKEN, RPC_URL, WALLET_ADDRESS, CHAIN_ID)
    bot.run()