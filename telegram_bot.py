import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from web3 import Web3
import asyncio
from typing import List, Dict, Optional
from datetime import datetime

load_dotenv()

from PoolManager import LiquidityPoolTracker
from database import Database

# Conversation states
WAITING_ADDRESS, WAITING_ALIAS, WAITING_BROADCAST_MESSAGE = range(3)


class TelegramLPBot:
    def __init__(self, token: str, rpc_url: str, chain_id: int = 999, admin_ids: List[int] = None, monitor_interval: int = 60):
        self.token = token
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.tracker = LiquidityPoolTracker(rpc_url, chain_id, delay_between_calls=1.0)
        self.db = Database()
        self.admin_ids = admin_ids or []
        self.monitor_interval = monitor_interval
        self.application = None

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
        context.user_data['adding_wallet'] = False
        context.user_data['adding_alias'] = True

        await update.message.reply_text(
            f"✅ Address validated!\n`{address}`\n\n"
            f"Do you want to add an alias for this wallet?\n\n"
            f"Send an alias (e.g., 'Main Wallet') or /skip to continue without alias.",
            parse_mode='Markdown'
        )
        return WAITING_ALIAS

    async def receive_alias(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        alias = update.message.text.strip()
        address = context.user_data.get('pending_address')

        if not address:
            await update.message.reply_text("❌ Error: No pending address. Please start over with /add")
            context.user_data.clear()
            return ConversationHandler.END

        try:
            success = self.db.add_wallet(user_id, address, alias)

            if success:
                display_name = self.db.get_wallet_display_name(address, alias)
                success_msg = (
                    f"✅ *Wallet added successfully!*\n\n"
                    f"📍 {display_name}\n\n"
                    f"You can now view positions for this wallet!"
                )
                await update.message.reply_text(
                    success_msg,
                    parse_mode='Markdown',
                    reply_markup=self.get_main_keyboard()
                )
            else:
                await update.message.reply_text(
                    "❌ *Error: This wallet is already registered!*\n\n"
                    "Use /wallets to view your wallets.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            await update.message.reply_text(
                f"❌ *Error adding wallet:*\n`{str(e)}`\n\n"
                "Please try again with /add",
                parse_mode='Markdown'
            )

        context.user_data.clear()
        return ConversationHandler.END

    async def skip_alias(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        address = context.user_data.get('pending_address')

        if not address:
            await update.message.reply_text("❌ Error: No pending address. Please start over with /add")
            context.user_data.clear()
            return ConversationHandler.END

        try:
            success = self.db.add_wallet(user_id, address, None)

            if success:
                display_name = self.db.get_wallet_display_name(address, None)
                success_msg = (
                    f"✅ *Wallet added successfully!*\n\n"
                    f"📍 {display_name}\n\n"
                    f"You can now view positions for this wallet!"
                )
                await update.message.reply_text(
                    success_msg,
                    parse_mode='Markdown',
                    reply_markup=self.get_main_keyboard()
                )
            else:
                await update.message.reply_text(
                    "❌ *Error: This wallet is already registered!*\n\n"
                    "Use /wallets to view your wallets.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            await update.message.reply_text(
                f"❌ *Error adding wallet:*\n`{str(e)}`\n\n"
                "Please try again with /add",
                parse_mode='Markdown'
            )

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
            notif_status = "🔔" if wallet.get('notifications_enabled', True) else "🔕"
            msg += f"{status} {notif_status} {display_name}\n"

            button_text = f"{'✅' if wallet['is_active'] else '👁️'} {wallet['alias'] or wallet['address'][:8]}..."
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"select_{wallet['address']}")
            ])

        keyboard.append([
            InlineKeyboardButton("➕ Add Wallet", callback_data="add_wallet"),
            InlineKeyboardButton("🔔 Notifications", callback_data="manage_notifications")
        ])
        keyboard.append([
            InlineKeyboardButton("🗑️ Delete", callback_data="delete_wallet")
        ])

        msg += "\n🔔 = Notifications ON\n🔕 = Notifications OFF"

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
        text = update.message.text

        # Check if we're in "adding wallet" mode
        if context.user_data.get('adding_wallet'):
            # This is an address
            if Web3.is_address(text.strip()):
                return await self.receive_address(update, context)
            else:
                await update.message.reply_text("❌ Invalid address format. Please send a valid address starting with 0x")
                return

        # Check if we're in "adding alias" mode
        if context.user_data.get('adding_alias'):
            return await self.receive_alias(update, context)

        # Normal menu handling
        if not self.db.get_active_wallet(user_id):
            await update.message.reply_text(
                "❌ No active wallet configured. Use /start to add one."
            )
            return

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

        # Handle broadcast confirmation
        if query.data in ['broadcast_confirm', 'broadcast_cancel']:
            await self.broadcast_confirm_handler(update, context)
            return

        # Handle notification management
        if query.data == 'manage_notifications':
            await query.answer()
            wallets = self.db.get_user_wallets(user_id)

            keyboard = []
            for wallet in wallets:
                display_name = self.db.get_wallet_display_name(wallet['address'], wallet['alias'])
                notif_status = "🔔" if wallet.get('notifications_enabled', True) else "🔕"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{notif_status} {display_name}",
                        callback_data=f"toggle_notif_{wallet['address']}"
                    )
                ])

            keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_wallets")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.edit_text(
                "🔔 *Notification Settings*\n\n"
                "Toggle notifications for each wallet:\n"
                "🔔 = ON | 🔕 = OFF",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        if query.data.startswith('toggle_notif_'):
            address = query.data.replace('toggle_notif_', '')
            wallets = self.db.get_user_wallets(user_id)
            wallet = next((w for w in wallets if w['address'] == address), None)

            if wallet:
                new_state = not wallet.get('notifications_enabled', True)
                self.db.toggle_notifications(user_id, address, new_state)

                status = "enabled" if new_state else "disabled"
                await query.answer(f"✅ Notifications {status}!")

                # Refresh the notification management view
                wallets = self.db.get_user_wallets(user_id)
                keyboard = []
                for w in wallets:
                    display_name = self.db.get_wallet_display_name(w['address'], w['alias'])
                    notif_status = "🔔" if w.get('notifications_enabled', True) else "🔕"
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{notif_status} {display_name}",
                            callback_data=f"toggle_notif_{w['address']}"
                        )
                    ])

                keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_wallets")])
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.message.edit_reply_markup(reply_markup=reply_markup)
            return

        if query.data == 'back_to_wallets':
            await query.answer()
            # Recreate the wallets view
            wallets = self.db.get_user_wallets(user_id)

            msg = "💼 *Your Wallets:*\n\n"
            keyboard = []

            for wallet in wallets:
                display_name = self.db.get_wallet_display_name(wallet['address'], wallet['alias'])
                status = "✅" if wallet['is_active'] else "⚪"
                notif_status = "🔔" if wallet.get('notifications_enabled', True) else "🔕"
                msg += f"{status} {notif_status} {display_name}\n"

                button_text = f"{'✅' if wallet['is_active'] else '👁️'} {wallet['alias'] or wallet['address'][:8]}..."
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data=f"select_{wallet['address']}")
                ])

            keyboard.append([
                InlineKeyboardButton("➕ Add Wallet", callback_data="add_wallet"),
                InlineKeyboardButton("🔔 Notifications", callback_data="manage_notifications")
            ])
            keyboard.append([
                InlineKeyboardButton("🗑️ Delete", callback_data="delete_wallet")
            ])

            msg += "\n🔔 = Notifications ON\n🔕 = Notifications OFF"

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
            return

        if query.data.startswith('select_'):
            address = query.data.replace('select_', '')
            self.db.set_active_wallet(user_id, address)
            await query.answer("✅ Wallet selected!")

            wallets = self.db.get_user_wallets(user_id)
            wallet_info = next((w for w in wallets if w['address'] == address), None)
            display_name = self.db.get_wallet_display_name(address, wallet_info['alias'] if wallet_info else None)

            await query.message.edit_text(
                f"✅ *Active wallet changed to:*\n{display_name}",
                parse_mode='Markdown'
            )

        elif query.data == 'add_wallet':
            await query.answer()
            context.user_data['adding_wallet'] = True
            context.user_data['adding_alias'] = False
            await query.message.reply_text(
                "📝 Send me the wallet address you want to add.\n\n"
                "Or send /cancel to abort.",
                parse_mode='Markdown'
            )

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

    async def monitor_positions(self, context: ContextTypes.DEFAULT_TYPE):
        """Background task to monitor positions"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Monitoring positions...")

        try:
            user_ids = self.db.get_all_user_ids()

            for user_id in user_ids:
                try:
                    wallets = self.db.get_user_wallets_for_monitoring(user_id)

                    for wallet in wallets:
                        address = wallet['address']

                        # Get positions for this wallet
                        positions = await asyncio.to_thread(
                            self.tracker.get_positions,
                            address,
                            include_pool_info=True
                        )

                        for position in positions:
                            if not position.get('pool_address'):
                                continue

                            pool_info = self.tracker.get_pool_current_tick(position['pool_address'])
                            if not pool_info:
                                continue

                            current_tick = pool_info['current_tick']
                            position_id = position['token_id']
                            in_range = position['tick_lower'] <= current_tick <= position['tick_upper']

                            if not in_range:
                                # Position is OUT OF RANGE
                                if not self.db.has_been_alerted(user_id, address, position_id):
                                    # Send alert
                                    await self.send_out_of_range_alert(user_id, wallet, position, pool_info)
                                    self.db.mark_as_alerted(user_id, address, position_id)
                            else:
                                # Position is back IN RANGE - clear alert
                                self.db.clear_position_alert(user_id, address, position_id)

                        # Small delay between wallets
                        await asyncio.sleep(2)

                except Exception as e:
                    print(f"Error monitoring user {user_id}: {e}")
                    continue

            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Monitoring complete")

        except Exception as e:
            print(f"Error in monitor_positions: {e}")

    async def send_out_of_range_alert(self, user_id: int, wallet: Dict, position: Dict, pool_info: Dict):
        """Send OUT OF RANGE alert to user"""
        token0_sym = position.get('token0_symbol', 'Token0')
        token1_sym = position.get('token1_symbol', 'Token1')
        wallet_display = self.db.get_wallet_display_name(wallet['address'], wallet.get('alias'))

        current_tick = pool_info['current_tick']

        alert_msg = (
            f"🚨 *OUT OF RANGE ALERT*\n\n"
            f"💼 Wallet: {wallet_display}\n"
            f"📌 Position #{position['token_id']}\n"
            f"🔄 Pair: *{token0_sym}/{token1_sym}*\n\n"
            f"📊 Range: {position['tick_lower']} to {position['tick_upper']}\n"
            f"🎯 Current Tick: {current_tick}\n"
            f"💰 Current Price: ${pool_info['price']:.6f}\n\n"
        )

        if current_tick < position['tick_lower']:
            alert_msg += f"⚠️ Price is *below* range (100% {token0_sym})\n"
        else:
            alert_msg += f"⚠️ Price is *above* range (100% {token1_sym})\n"

        alert_msg += f"\nUse /positions to view details."

        try:
            await self.application.bot.send_message(
                chat_id=user_id,
                text=alert_msg,
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Failed to send alert to {user_id}: {e}")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Operation cancelled.",
            reply_markup=self.get_main_keyboard()
        )
        return ConversationHandler.END

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.admin_ids

    async def broadcast_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start broadcast message (admin only)"""
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Access denied. Admin only.")
            return ConversationHandler.END

        total_users = len(self.db.get_all_user_ids())

        await update.message.reply_text(
            f"📢 *Broadcast Mode*\n\n"
            f"Send the message you want to broadcast to *{total_users} users*.\n\n"
            f"You can use Markdown formatting:\n"
            f"- `*bold*` → *bold*\n"
            f"- `_italic_` → _italic_\n"
            f"- `` `code` `` → `code`\n\n"
            f"Send /cancel to abort.",
            parse_mode='Markdown'
        )
        return WAITING_BROADCAST_MESSAGE

    async def receive_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and send broadcast message"""
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Access denied.")
            return ConversationHandler.END

        broadcast_message = update.message.text
        user_ids = self.db.get_all_user_ids()

        # Confirmation
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm & Send", callback_data="broadcast_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data['broadcast_message'] = broadcast_message

        await update.message.reply_text(
            f"📢 *Preview:*\n\n{broadcast_message}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Will be sent to: *{len(user_ids)} users*\n\n"
            f"Confirm?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        return ConversationHandler.END

    async def broadcast_confirm_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle broadcast confirmation"""
        query = update.callback_query
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await query.answer("❌ Access denied.")
            return

        if query.data == "broadcast_confirm":
            await query.answer()
            broadcast_message = context.user_data.get('broadcast_message')

            if not broadcast_message:
                await query.message.edit_text("❌ No message found. Please start over with /broadcast")
                return

            user_ids = self.db.get_all_user_ids()

            status_msg = await query.message.edit_text(
                f"📤 Sending broadcast to {len(user_ids)} users...\n"
                f"Progress: 0/{len(user_ids)}"
            )

            success_count = 0
            failed_count = 0

            for idx, target_user_id in enumerate(user_ids):
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"📢 *Announcement*\n\n{broadcast_message}",
                        parse_mode='Markdown'
                    )
                    success_count += 1

                    # Update progress every 10 users
                    if (idx + 1) % 10 == 0 or (idx + 1) == len(user_ids):
                        await status_msg.edit_text(
                            f"📤 Sending broadcast...\n"
                            f"Progress: {idx + 1}/{len(user_ids)}\n"
                            f"✅ Success: {success_count}\n"
                            f"❌ Failed: {failed_count}"
                        )

                    # Rate limiting
                    await asyncio.sleep(0.05)

                except Exception as e:
                    failed_count += 1
                    print(f"Failed to send to {target_user_id}: {e}")

            await status_msg.edit_text(
                f"✅ *Broadcast Complete!*\n\n"
                f"📊 Results:\n"
                f"✅ Sent: {success_count}\n"
                f"❌ Failed: {failed_count}\n"
                f"📊 Total: {len(user_ids)}",
                parse_mode='Markdown'
            )

            context.user_data.clear()

        elif query.data == "broadcast_cancel":
            await query.answer("Cancelled")
            await query.message.edit_text("❌ Broadcast cancelled.")
            context.user_data.clear()

    async def add_wallet_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the add wallet process"""
        await update.message.reply_text(
            "Send me the wallet address you want to add.\n\n",
            parse_mode='Markdown'
        )
        return WAITING_ADDRESS

    def run(self):
        self.application = Application.builder().token(self.token).build()

        # Main conversation for adding wallets
        add_wallet_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                CommandHandler("add", self.add_wallet_start)
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
            fallbacks=[CommandHandler("cancel", self.cancel)],
            per_message=False
        )

        # Broadcast conversation (admin only)
        broadcast_handler = ConversationHandler(
            entry_points=[CommandHandler("broadcast", self.broadcast_start)],
            states={
                WAITING_BROADCAST_MESSAGE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_broadcast)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            per_message=False
        )

        self.application.add_handler(add_wallet_handler)
        self.application.add_handler(broadcast_handler)
        self.application.add_handler(CommandHandler("wallets", self.my_wallets))
        self.application.add_handler(CommandHandler("positions", self.view_positions))
        self.application.add_handler(CommandHandler("alerts", self.out_of_range_positions))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

        # Schedule monitoring job
        job_queue = self.application.job_queue
        job_queue.run_repeating(
            self.monitor_positions,
            interval=self.monitor_interval * 60,
            first=60
        )

        print("🤖 Bot started!")
        print(f"🔍 Monitoring interval: {self.monitor_interval} minutes")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    RPC_URL = os.getenv('RPC_URL')
    CHAIN_ID = int(os.getenv('CHAIN_ID', '999'))
    MONITOR_INTERVAL = int(os.getenv('MONITOR_INTERVAL_MINUTES', '60'))

    # Parse admin IDs from environment variable
    admin_ids_str = os.getenv('ADMIN_USER_IDS', '')
    ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip().isdigit()]

    if not TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not defined in .env")
        exit(1)
    if not RPC_URL:
        print("❌ Error: RPC_URL not defined in .env")
        exit(1)

    bot = TelegramLPBot(TELEGRAM_TOKEN, RPC_URL, CHAIN_ID, ADMIN_IDS, MONITOR_INTERVAL)
    bot.run()