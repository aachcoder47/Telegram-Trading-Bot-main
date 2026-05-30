import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class Wallet:
    id: int
    chat_id: int
    wallet_address: str
    private_key_encrypted: str
    balance_usd: float
    created_at_utc: str
    updated_at_utc: str


@dataclass
class WalletTransaction:
    id: int
    wallet_id: int
    transaction_type: str
    amount: float
    currency: str
    fee: float
    status: str
    created_at_utc: str


@dataclass
class TradingPosition:
    id: int
    wallet_id: int
    token: str
    position_type: str
    entry_price: float
    quantity: float
    leverage: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    status: str
    opened_at_utc: str
    closed_at_utc: Optional[str]
    pnl: Optional[float]


def get_utc_now() -> str:
    """Get current UTC timestamp as ISO string"""
    return datetime.now(timezone.utc).isoformat()


def create_wallet(
    conn: sqlite3.Connection,
    chat_id: int,
    wallet_address: str,
    private_key_encrypted: str,
    busy_retries: int = 10,
    busy_sleep: float = 0.2,
) -> Wallet:
    """Create a new wallet in the database"""
    now = get_utc_now()
    sql = """
        INSERT INTO wallets (chat_id, wallet_address, private_key_encrypted, balance_usd, created_at_utc, updated_at_utc)
        VALUES (?, ?, ?, 0, ?, ?)
    """
    
    for attempt in range(busy_retries):
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (chat_id, wallet_address, private_key_encrypted, now, now))
            conn.commit()
            
            # Return the created wallet
            cursor.execute(
                "SELECT id, chat_id, wallet_address, private_key_encrypted, balance_usd, created_at_utc, updated_at_utc FROM wallets WHERE id = ?",
                (cursor.lastrowid,)
            )
            row = cursor.fetchone()
            
            return Wallet(
                id=row[0],
                chat_id=row[1],
                wallet_address=row[2],
                private_key_encrypted=row[3],
                balance_usd=row[4],
                created_at_utc=row[5],
                updated_at_utc=row[6],
            )
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < busy_retries - 1:
                import time
                time.sleep(busy_sleep)
                continue
            raise


def get_wallet_by_chat_id(
    conn: sqlite3.Connection,
    chat_id: int,
    busy_retries: int = 10,
    busy_sleep: float = 0.2,
) -> Optional[Wallet]:
    """Get a wallet by chat ID"""
    sql = "SELECT id, chat_id, wallet_address, private_key_encrypted, balance_usd, created_at_utc, updated_at_utc FROM wallets WHERE chat_id = ?"
    
    for attempt in range(busy_retries):
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (chat_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return Wallet(
                id=row[0],
                chat_id=row[1],
                wallet_address=row[2],
                private_key_encrypted=row[3],
                balance_usd=row[4],
                created_at_utc=row[5],
                updated_at_utc=row[6],
            )
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < busy_retries - 1:
                import time
                time.sleep(busy_sleep)
                continue
            raise


def get_wallet_by_address(
    conn: sqlite3.Connection,
    wallet_address: str,
    busy_retries: int = 10,
    busy_sleep: float = 0.2,
) -> Optional[Wallet]:
    """Get a wallet by wallet address"""
    sql = "SELECT id, chat_id, wallet_address, private_key_encrypted, balance_usd, created_at_utc, updated_at_utc FROM wallets WHERE wallet_address = ?"
    
    for attempt in range(busy_retries):
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (wallet_address,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return Wallet(
                id=row[0],
                chat_id=row[1],
                wallet_address=row[2],
                private_key_encrypted=row[3],
                balance_usd=row[4],
                created_at_utc=row[5],
                updated_at_utc=row[6],
            )
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < busy_retries - 1:
                import time
                time.sleep(busy_sleep)
                continue
            raise


def update_wallet_balance(
    conn: sqlite3.Connection,
    wallet_id: int,
    new_balance: float,
    busy_retries: int = 10,
    busy_sleep: float = 0.2,
) -> bool:
    """Update wallet balance"""
    sql = "UPDATE wallets SET balance_usd = ?, updated_at_utc = ? WHERE id = ?"
    now = get_utc_now()
    
    for attempt in range(busy_retries):
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (new_balance, now, wallet_id))
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < busy_retries - 1:
                import time
                time.sleep(busy_sleep)
                continue
            raise


def create_transaction(
    conn: sqlite3.Connection,
    wallet_id: int,
    transaction_type: str,
    amount: float,
    currency: str,
    fee: float = 0.0,
    status: str = "completed",
    busy_retries: int = 10,
    busy_sleep: float = 0.2,
) -> WalletTransaction:
    """Create a wallet transaction"""
    now = get_utc_now()
    sql = """
        INSERT INTO wallet_transactions (wallet_id, transaction_type, amount, currency, fee, status, created_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    
    for attempt in range(busy_retries):
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (wallet_id, transaction_type, amount, currency, fee, status, now))
            conn.commit()
            
            cursor.execute(
                "SELECT id, wallet_id, transaction_type, amount, currency, fee, status, created_at_utc FROM wallet_transactions WHERE id = ?",
                (cursor.lastrowid,)
            )
            row = cursor.fetchone()
            
            return WalletTransaction(
                id=row[0],
                wallet_id=row[1],
                transaction_type=row[2],
                amount=row[3],
                currency=row[4],
                fee=row[5],
                status=row[6],
                created_at_utc=row[7],
            )
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < busy_retries - 1:
                import time
                time.sleep(busy_sleep)
                continue
            raise


def get_wallet_transactions(
    conn: sqlite3.Connection,
    wallet_id: int,
    limit: int = 50,
    busy_retries: int = 10,
    busy_sleep: float = 0.2,
) -> List[WalletTransaction]:
    """Get wallet transactions"""
    sql = """
        SELECT id, wallet_id, transaction_type, amount, currency, fee, status, created_at_utc
        FROM wallet_transactions
        WHERE wallet_id = ?
        ORDER BY created_at_utc DESC
        LIMIT ?
    """
    
    for attempt in range(busy_retries):
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (wallet_id, limit))
            rows = cursor.fetchall()
            
            return [
                WalletTransaction(
                    id=row[0],
                    wallet_id=row[1],
                    transaction_type=row[2],
                    amount=row[3],
                    currency=row[4],
                    fee=row[5],
                    status=row[6],
                    created_at_utc=row[7],
                )
                for row in rows
            ]
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < busy_retries - 1:
                import time
                time.sleep(busy_sleep)
                continue
            raise


def create_trading_position(
    conn: sqlite3.Connection,
    wallet_id: int,
    token: str,
    position_type: str,
    entry_price: float,
    quantity: float,
    leverage: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    busy_retries: int = 10,
    busy_sleep: float = 0.2,
) -> TradingPosition:
    """Create a trading position"""
    now = get_utc_now()
    sql = """
        INSERT INTO trading_positions (wallet_id, token, position_type, entry_price, quantity, leverage, stop_loss, take_profit, status, opened_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
    """
    
    for attempt in range(busy_retries):
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (wallet_id, token.upper(), position_type.lower(), entry_price, quantity, leverage, stop_loss, take_profit, now))
            conn.commit()
            
            cursor.execute(
                "SELECT id, wallet_id, token, position_type, entry_price, quantity, leverage, stop_loss, take_profit, status, opened_at_utc, closed_at_utc, pnl FROM trading_positions WHERE id = ?",
                (cursor.lastrowid,)
            )
            row = cursor.fetchone()
            
            return TradingPosition(
                id=row[0],
                wallet_id=row[1],
                token=row[2],
                position_type=row[3],
                entry_price=row[4],
                quantity=row[5],
                leverage=row[6],
                stop_loss=row[7],
                take_profit=row[8],
                status=row[9],
                opened_at_utc=row[10],
                closed_at_utc=row[11],
                pnl=row[12],
            )
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < busy_retries - 1:
                import time
                time.sleep(busy_sleep)
                continue
            raise


def get_open_positions(
    conn: sqlite3.Connection,
    wallet_id: int,
    busy_retries: int = 10,
    busy_sleep: float = 0.2,
) -> List[TradingPosition]:
    """Get open trading positions for a wallet"""
    sql = """
        SELECT id, wallet_id, token, position_type, entry_price, quantity, leverage, stop_loss, take_profit, status, opened_at_utc, closed_at_utc, pnl
        FROM trading_positions
        WHERE wallet_id = ? AND status = 'open'
        ORDER BY opened_at_utc DESC
    """
    
    for attempt in range(busy_retries):
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (wallet_id,))
            rows = cursor.fetchall()
            
            return [
                TradingPosition(
                    id=row[0],
                    wallet_id=row[1],
                    token=row[2],
                    position_type=row[3],
                    entry_price=row[4],
                    quantity=row[5],
                    leverage=row[6],
                    stop_loss=row[7],
                    take_profit=row[8],
                    status=row[9],
                    opened_at_utc=row[10],
                    closed_at_utc=row[11],
                    pnl=row[12],
                )
                for row in rows
            ]
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < busy_retries - 1:
                import time
                time.sleep(busy_sleep)
                continue
            raise


def close_trading_position(
    conn: sqlite3.Connection,
    position_id: int,
    pnl: float,
    busy_retries: int = 10,
    busy_sleep: float = 0.2,
) -> bool:
    """Close a trading position"""
    sql = "UPDATE trading_positions SET status = 'closed', closed_at_utc = ?, pnl = ? WHERE id = ?"
    now = get_utc_now()
    
    for attempt in range(busy_retries):
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (now, pnl, position_id))
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < busy_retries - 1:
                import time
                time.sleep(busy_sleep)
                continue
            raise
