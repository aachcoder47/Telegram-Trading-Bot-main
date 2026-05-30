import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def connect_db(db_path: str) -> sqlite3.Connection:
    """Connect to SQLite database"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize SQLite database with required tables"""
    conn = connect_db(db_path)
    
    # Create tables
    create_tables(conn)
    
    return conn


def create_tables(conn: sqlite3.Connection):
    """Create all required database tables"""
    cursor = conn.cursor()
    
    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            text TEXT,
            timestamp_utc TEXT NOT NULL,
            UNIQUE(channel_id, message_id)
        )
    """)
    
    # Media files table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        )
    """)
    
    # Trade signals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            token TEXT NOT NULL,
            position_type TEXT NOT NULL,
            entry_price REAL,
            leverage REAL,
            stop_losses TEXT,
            take_profits TEXT,
            confidence REAL,
            extracted_at_utc TEXT NOT NULL,
            UNIQUE(channel_id, message_id)
        )
    """)
    
    # Submitted positions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submitted_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER NOT NULL,
            exchange TEXT NOT NULL,
            symbol TEXT NOT NULL,
            position_type TEXT NOT NULL,
            entry_price REAL,
            quantity REAL,
            leverage REAL,
            stop_loss REAL,
            take_profit REAL,
            status TEXT NOT NULL,
            submitted_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        )
    """)
    
    # Wallets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            wallet_address TEXT NOT NULL UNIQUE,
            private_key_encrypted TEXT NOT NULL,
            balance_usd REAL DEFAULT 0,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            UNIQUE(chat_id, wallet_address)
        )
    """)
    
    # Wallet transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            fee REAL DEFAULT 0,
            status TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            FOREIGN KEY (wallet_id) REFERENCES wallets(id)
        )
    """)
    
    # Trading positions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trading_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_id INTEGER NOT NULL,
            token TEXT NOT NULL,
            position_type TEXT NOT NULL,
            entry_price REAL NOT NULL,
            quantity REAL NOT NULL,
            leverage REAL,
            stop_loss REAL,
            take_profit REAL,
            status TEXT NOT NULL,
            opened_at_utc TEXT NOT NULL,
            closed_at_utc TEXT,
            pnl REAL,
            FOREIGN KEY (wallet_id) REFERENCES wallets(id)
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp_utc)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_channel ON trade_signals(channel_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_chat_id ON wallets(chat_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallet_transactions_wallet ON wallet_transactions(wallet_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trading_positions_wallet ON trading_positions(wallet_id)")
    
    conn.commit()
    logger.info("Database tables created successfully")


def get_utc_now() -> str:
    """Get current UTC timestamp as ISO string"""
    return datetime.now(timezone.utc).isoformat()
