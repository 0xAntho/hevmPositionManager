import sqlite3
from typing import List, Dict, Optional
from web3 import Web3
import threading


class Database:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self.local = threading.local()
        self.init_db()

    def get_connection(self):
        """Get thread-local database connection"""
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
            self.local.conn.execute("PRAGMA journal_mode=WAL")
        return self.local.conn

    def init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                address TEXT NOT NULL,
                alias TEXT,
                is_active BOOLEAN DEFAULT 0,
                notifications_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, address)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                wallet_address TEXT NOT NULL,
                position_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                alerted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                out_of_range_since TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, wallet_address, position_id, alert_type)
            )
        """)

        conn.commit()
        conn.close()

    def add_user(self, user_id: int):
        """Add a new user"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()

    def add_wallet(self, user_id: int, address: str, alias: Optional[str] = None) -> bool:
        """Add a wallet for a user"""
        self.add_user(user_id)

        address = Web3.to_checksum_address(address)

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO wallets (user_id, address, alias) VALUES (?, ?, ?)",
                (user_id, address, alias)
            )
            conn.commit()

            # Set as active if it's the first wallet
            cursor.execute("SELECT COUNT(*) FROM wallets WHERE user_id = ?", (user_id,))
            if cursor.fetchone()[0] == 1:
                self.set_active_wallet(user_id, address)

            return True
        except sqlite3.IntegrityError:
            conn.rollback()
            return False

    def get_user_wallets(self, user_id: int) -> List[Dict]:
        """Get all wallets for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, address, alias, is_active 
            FROM wallets 
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))

        wallets = []
        for row in cursor.fetchall():
            wallets.append({
                'id': row[0],
                'address': row[1],
                'alias': row[2],
                'is_active': bool(row[3])
            })

        return wallets

    def get_active_wallet(self, user_id: int) -> Optional[str]:
        """Get the active wallet address for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT address 
            FROM wallets 
            WHERE user_id = ? AND is_active = 1
        """, (user_id,))

        result = cursor.fetchone()
        return result[0] if result else None

    def set_active_wallet(self, user_id: int, address: str):
        """Set a wallet as active"""
        address = Web3.to_checksum_address(address)

        conn = self.get_connection()
        cursor = conn.cursor()

        # Deactivate all wallets for this user
        cursor.execute("UPDATE wallets SET is_active = 0 WHERE user_id = ?", (user_id,))

        # Activate the selected wallet
        cursor.execute(
            "UPDATE wallets SET is_active = 1 WHERE user_id = ? AND address = ?",
            (user_id, address)
        )

        conn.commit()

    def delete_wallet(self, user_id: int, address: str) -> bool:
        """Delete a wallet"""
        address = Web3.to_checksum_address(address)

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM wallets WHERE user_id = ? AND address = ?",
            (user_id, address)
        )

        deleted = cursor.rowcount > 0
        conn.commit()

        return deleted

    def update_alias(self, user_id: int, address: str, alias: str):
        """Update wallet alias"""
        address = Web3.to_checksum_address(address)

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE wallets SET alias = ? WHERE user_id = ? AND address = ?",
            (alias, user_id, address)
        )

        conn.commit()

    def get_wallet_display_name(self, address: str, alias: Optional[str] = None) -> str:
        """Get display name for a wallet"""
        if alias:
            return f"{alias} ({address[:6]}...{address[-4:]})"
        return f"{address[:6]}...{address[-4:]}"

    def get_all_user_ids(self) -> List[int]:
        """Get all user IDs that have registered with the bot"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT user_id FROM users ORDER BY created_at")

        user_ids = [row[0] for row in cursor.fetchall()]
        return user_ids

    def get_user_wallets_for_monitoring(self, user_id: int) -> List[Dict]:
        """Get wallets with notifications enabled for monitoring"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT address, alias, notifications_enabled, is_active
            FROM wallets 
            WHERE user_id = ? AND notifications_enabled = 1
            ORDER BY created_at DESC
        """, (user_id,))

        wallets = []
        for row in cursor.fetchall():
            wallets.append({
                'address': row[0],
                'alias': row[1],
                'notifications_enabled': bool(row[2]),
                'is_active': bool(row[3])
            })

        return wallets

    def has_been_alerted(self, user_id: int, wallet_address: str, position_id: int, alert_type: str = 'out_of_range') -> bool:
        """Check if user has already been alerted for this position"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM position_alerts 
            WHERE user_id = ? AND wallet_address = ? AND position_id = ? AND alert_type = ?
        """, (user_id, wallet_address, position_id, alert_type))

        return cursor.fetchone()[0] > 0

    def mark_as_alerted(self, user_id: int, wallet_address: str, position_id: int, alert_type: str = 'out_of_range', out_of_range_since: str = None):
        """Mark that user has been alerted for this position"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO position_alerts (user_id, wallet_address, position_id, alert_type, out_of_range_since, alerted_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, wallet_address, position_id, alert_type, out_of_range_since))

        conn.commit()

    def clear_position_alert(self, user_id: int, wallet_address: str, position_id: int, alert_type: str = None):
        """Clear alert for position (when it comes back in range)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if alert_type:
            cursor.execute("""
                DELETE FROM position_alerts 
                WHERE user_id = ? AND wallet_address = ? AND position_id = ? AND alert_type = ?
            """, (user_id, wallet_address, position_id, alert_type))
        else:
            cursor.execute("""
                DELETE FROM position_alerts 
                WHERE user_id = ? AND wallet_address = ? AND position_id = ?
            """, (user_id, wallet_address, position_id))

        conn.commit()

    def get_out_of_range_since(self, user_id: int, wallet_address: str, position_id: int) -> Optional[str]:
        """Get timestamp when position went out of range"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT out_of_range_since FROM position_alerts 
            WHERE user_id = ? AND wallet_address = ? AND position_id = ? AND alert_type = 'out_of_range'
        """, (user_id, wallet_address, position_id))

        result = cursor.fetchone()
        return result[0] if result else None

    def toggle_notifications(self, user_id: int, address: str, enabled: bool):
        """Enable/disable notifications for a wallet"""
        address = Web3.to_checksum_address(address)

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE wallets SET notifications_enabled = ? WHERE user_id = ? AND address = ?",
            (1 if enabled else 0, user_id, address)
        )

        conn.commit()