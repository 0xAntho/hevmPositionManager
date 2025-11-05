import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from web3 import Web3
import asyncio
from typing import List, Dict, Optional

load_dotenv()

from PoolManager import LiquidityPoolTracker
from database import Database

# Conversation states
WAITING_ADDRESS, WAITING_ALIAS, WAITING_NEW_ALIAS = range(3)


class TelegramLPBot:
    def __init__(self, token: str, rpc_url: str, chain_id: int = 999):
        self.token = token
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.tracker = LiquidityPoolTracker(rpc_url, chain_id, delay_between_calls=1.0)
        self.db = Database()

    def get_main_keyboard(self):
        keyboard = [
            [KeyboardButton("📊 My Positions"), KeyboardButton("🔄 Refresh")],
            [KeyboardButton("⚠️ Alerts"), KeyboardButton("💼 My Wallets")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        wallets = self.db.get_user_wallets(user_id)

        if wallets:
            active_wallet = self.db.get_active_wallet(user_id)
            welcome_msg = (
                f"👋 *Welcome back!*\n\n"
                f"📍 Active wallet:\n`{active_wallet}`\n\n"
                f"Use /wallets to manage your wallets."
            )
            await update.message.reply_text(
                welcome_msg,
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )
            return ConversationHandler.END

        welcome_msg = (
            f"🤖 *Welcome to LP Position Tracker!*\n\n"
            f"🔗 Chain: Hyperliquid EVM (ID: {self.chain_id})\n\n"
            f"To get started, send me a wallet address.\n\n"
            f"📝 Format: `0x...`"
        )
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
        return WAITING_ADDRESS

    async def receive_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        address = update.message.text.strip()

        if not Web3.is_address(address):
            await update.message.reply_text(
                "❌ Invalid address. Please send a valid Ethereum address starting with 0x"
            )
            return WAITING_ADDRESS

        address = Web3.to_checksum_address(address)
        context.user_data['pending_address'] = address

        await update.message.reply_text(
            f"✅ Address validated!\n\n"
            f"Do you want to add an alias for this wallet?\n\n"
            f"Send an alias (e.g., 'Main Wallet') or /skip to continue without alias."
        )
        return WAITING_ALIAS

    async def receive_alias(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        alias = update.message.text.strip()
        address = context.user_data.get('pending_address')

        success = self.db.add_wallet(user_id, address, alias)

        if success:
            success_msg = (
                f"✅ *Wallet added successfully!*\n\n"
                f"📍 Address: `{address}`\n"
                f"🏷️ Alias: {alias}\n\n"
                f"Use the buttons below to interact:"
            )
            await update.message.reply_text(
                success_msg,
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )
        else:
            await update.message.reply_text("❌ This wallet is already registered!")

        context.user_data.clear()
        return ConversationHandler.END

    async def skip_alias(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        address = context.user_data.get('pending_address')

        success = self.db.add_wallet(user_id, address, None)

        if success:
            success_msg = (
                f"✅ *Wallet added successfully!*\n\n"
                f"📍 Address: `{address}`\n\n"
                f"Use the buttons below to interact:"
            )
            await update.message.reply_text(
                success_msg,
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )
        else:
            await update.message.reply_text("❌ This wallet is already registered!")

        context.user_data.clear()
        return ConversationHandler.END

    async def my_wallets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        wallets = self.db.get_user_wallets(user_id)

        if not wallets:
            await update.message.reply_text(
                "❌ No wallets registered. Use /add to add a wallet."
            )
            return

        msg = "💼 *Your Wallets:*\n\n"
        keyboard = []

        for wallet in wallets:
            display_name = self.db.get_wallet_display_name(wallet['address'], wallet['alias'])
            status = "✅" if wallet['is_active'] else "⚪"
            msg += f"{status} {display_name}\n"

            keyboard.append([
                InlineKeyboardButton(
                    f"{'✅' if wallet['is_active'] else '👁️'} {wallet['alias'] or wallet['address'][:8]}...",
                    callback_data=f"select_{wallet['address']}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("➕ Add Wallet", callback_data="add_wallet"),
            InlineKeyboardButton("🗑️ Delete", callback_data="delete_wallet")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

    async def view_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        wallet_address = self.db.get_active_wallet(user_id)

        if not wallet_address:
            await update.message.reply_text(
                "❌ No active wallet. Use /wallets to select or add a wallet."
            )
            return

        if update.callback_query:
            query = update.callback_query
            await query.answer()
            message = query.message
        else:
            message = update.message

        loading_msg = await message.reply_text("⏳ Fetching positions...")

        try:
            positions = await asyncio.to_thread(
                self.tracker.get_positions,
                wallet_address,
                include_pool_info=True
            )

            if not positions:
                await loading_msg.edit_text("❌ No active positions found.")
                return

            for position in positions:
                msg = self._format_position(position)
                keyboard = [[
                    InlineKeyboardButton("🔍 Details", callback_data=f'details_{position["token_id"]}')
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

            await loading_msg.delete()

            summary = f"✅ *{len(positions)} active position(s) found*"
            await message.reply_text(summary, parse_mode='Markdown')

        except Exception as e:
            await loading_msg.edit_text(f"❌ Error: {str(e)}")

    async def out_of_range_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        wallet_address = self.db.get_active_wallet(user_id)

        if not wallet_address:
            await update.message.reply_text(
                "❌ No active wallet. Use /wallets to select or add a wallet."
            )
            return

        if update.callback_query:
            query = update.callback_query
            await query.answer()
            message = query.message
        else:
            message = update.message

        loading_msg = await message.reply_text("⏳ Checking positions...")

        try:
            positions = await asyncio.to_thread(
                self.tracker.get_positions,
                wallet_address,
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

            await loading_msg.delete()

            if not out_of_range:
                await message.reply_text("✅ All positions are IN RANGE! 🎉")
                return

            alert_msg = f"⚠️ *ALERT: {len(out_of_range)} position(s) OUT OF RANGE*\n\n"
            await message.reply_text(alert_msg, parse_mode='Markdown')

            for position in out_of_range:
                msg = self._format_position(position, alert_mode=True)
                await message.reply_text(msg, parse_mode='Markdown')

        except Exception as e:
            await loading_msg.edit_text(f"❌ Error: {str(e)}")

    def _format_position(self, position: Dict, alert_mode: bool = False) -> str:
        token0_sym = position.get('token0_symbol', 'Token0')
        token1_sym = position.get('token1_symbol', 'Token1')

        header = f"🚨 *Position #{position['token_id']}* - OUT OF RANGE\n" if alert_mode else f"💼 *Position #{position['token_id']}*\n"

        msg = header
        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"📌 Pair: *{token0_sym}/{token1_sym}*\n"
        msg += f"💰 Fee: {position['fee'] / 10000}%\n\n"

        msg += f"📊 *Liquidity Range:*\n"
        msg += f"  Lower: {position['tick_lower']} (${position['price_lower']:.6f})\n"
        msg += f"  Upper: {position['tick_upper']} (${position['price_upper']:.6f})\n\n"

        if position.get('pool_address'):
            pool_info = self.tracker.get_pool_current_tick(position['pool_address'])
            if pool_info:
                current_tick = pool_info['current_tick']
                in_range = position['tick_lower'] <= current_tick <= position['tick_upper']

                msg += f"🎯 *Current State:*\n"
                msg += f"  Tick: {current_tick}\n"
                msg += f"  Price: ${pool_info['price']:.6f}\n"

                if in_range:
                    msg += f"  Status: ✅ IN RANGE\n\n"
                else:
                    msg += f"  Status: ⚠️ OUT OF RANGE\n"
                    if current_tick < position['tick_lower']:
                        msg += f"  → Price below range (100% {token0_sym})\n\n"
                    else:
                        msg += f"  → Price above range (100% {token1_sym})\n\n"

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

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if not self.db.get_active_wallet(user_id):
            await update.message.reply_text(
                "❌ No active wallet configured. Use /start to add one."
            )
            return

        text = update.message.text

        if text == "📊 My Positions":
            await self.view_positions(update, context)
        elif text == "🔄 Refresh":
            await self.view_positions(update, context)
        elif text == "⚠️ Alerts":
            await self.out_of_range_positions(update, context)
        elif text == "💼 My Wallets":
            await self.my_wallets(update, context)

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id

        if query.data.startswith('select_'):
            address = query.data.replace('select_', '')
            self.db.set_active_wallet(user_id, address)
            await query.answer("✅ Wallet selected!")

            wallets = self.db.get_user_wallets(user_id)
            wallet_info = next((w for w in wallets if w['address'] == address), None)
            display_name = self.db.get_wallet_display_name(address, wallet_info['alias'] if wallet_info else None)

            await query.message.edit_text(
                f"✅ Active wallet changed to:\n{display_name}",
                parse_mode='Markdown'
            )

        elif query.data == 'add_wallet':
            await query.answer()
            await query.message.reply_text(
                "Send me the wallet address you want to add.\n\n"
                "📝 Format: `0x...`",
                parse_mode='Markdown'
            )
            return WAITING_ADDRESS

        elif query.data == 'delete_wallet':
            await query.answer()
            wallets = self.db.get_user_wallets(user_id)

            if len(wallets) <= 1:
                await query.message.reply_text("❌ You must keep at least one wallet!")
                return

            keyboard = []
            for wallet in wallets:
                display_name = self.db.get_wallet_display_name(wallet['address'], wallet['alias'])
                keyboard.append([
                    InlineKeyboardButton(
                        f"🗑️ {display_name}",
                        callback_data=f"confirm_delete_{wallet['address']}"
                    )
                ])

            keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.edit_text(
                "Select a wallet to delete:",
                reply_markup=reply_markup
            )

        elif query.data.startswith('confirm_delete_'):
            address = query.data.replace('confirm_delete_', '')

            active = self.db.get_active_wallet(user_id)
            self.db.delete_wallet(user_id, address)

            if active == address:
                wallets = self.db.get_user_wallets(user_id)
                if wallets:
                    self.db.set_active_wallet(user_id, wallets[0]['address'])

            await query.answer("✅ Wallet deleted!")
            await query.message.edit_text("✅ Wallet deleted successfully!")

        elif query.data == 'cancel_delete':
            await query.answer()
            await query.message.edit_text("❌ Deletion cancelled.")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("❌ Operation cancelled.")
        return ConversationHandler.END

    def run(self):
        application = Application.builder().token(self.token).build()

        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                CommandHandler("add", self.start)
            ],
            states={
                WAITING_ADDRESS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_address)
                ],
                WAITING_ALIAS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_alias),
                    CommandHandler("skip", self.skip_alias)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )

        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("wallets", self.my_wallets))
        application.add_handler(CommandHandler("positions", self.view_positions))
        application.add_handler(CommandHandler("alerts", self.out_of_range_positions))
        application.add_handler(CallbackQueryHandler(self.button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

        print("🤖 Bot started!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    RPC_URL = os.getenv('RPC_URL')
    CHAIN_ID = int(os.getenv('CHAIN_ID', '999'))

    if not TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not defined in .env")
        exit(1)
    if not RPC_URL:
        print("❌ Error: RPC_URL not defined in .env")
        exit(1)

    bot = TelegramLPBot(TELEGRAM_TOKEN, RPC_URL, CHAIN_ID)
    bot.run()