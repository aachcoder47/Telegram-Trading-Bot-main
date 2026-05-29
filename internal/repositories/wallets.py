from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List
from internal.db.sqlite import sql_execute_with_retry


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
    transaction_type: str  # 'deposit', 'withdraw', 'trade', 'fee'
    amount: float
    currency: str
    fee: float
    status: str
    transaction_hash: Optional[str]
    created_at_utc: str


@dataclass
class TradingPosition:
    id: int
    wallet_id: int
    token: str
    position_type: str  # 'long' or 'short'
    entry_price: float
    quantity: float
    leverage: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    status: str  # 'open', 'closed', 'liquidated'
    pnl: float
    opened_at_utc: str
    closed_at_utc: Optional[str]


def create_wallet(
    conn,
    chat_id: int,
    wallet_address: str,
    private_key_encrypted: str,
    busy_retries: int,
    busy_sleep_secs: float,
) -> Wallet:
    now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    sql = """
    INSERT INTO wallets (chat_id, wallet_address, private_key_encrypted, balance_usd, created_at_utc, updated_at_utc)
    VALUES (?, ?, ?, 0, ?, ?)
    RETURNING id, chat_id, wallet_address, private_key_encrypted, balance_usd, created_at_utc, updated_at_utc;
    """
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (chat_id, wallet_address, private_key_encrypted, now, now))
        row = cursor.fetchone()
        conn.commit()
        return Wallet(
            id=row[0],
            chat_id=row[1],
            wallet_address=row[2],
            private_key_encrypted=row[3],
            balance_usd=row[4],
            created_at_utc=row[5],
            updated_at_utc=row[6],
        )
    finally:
        cursor.close()


def get_wallet_by_chat_id(
    conn, chat_id: int, busy_retries: int, busy_sleep_secs: float
) -> Optional[Wallet]:
    sql = "SELECT id, chat_id, wallet_address, private_key_encrypted, balance_usd, created_at_utc, updated_at_utc FROM wallets WHERE chat_id = ?"
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (chat_id,))
        row = cursor.fetchone()
        if row:
            return Wallet(
                id=row[0],
                chat_id=row[1],
                wallet_address=row[2],
                private_key_encrypted=row[3],
                balance_usd=row[4],
                created_at_utc=row[5],
                updated_at_utc=row[6],
            )
        return None
    finally:
        cursor.close()


def get_wallet_by_address(
    conn, wallet_address: str, busy_retries: int, busy_sleep_secs: float
) -> Optional[Wallet]:
    sql = "SELECT id, user_id, wallet_address, private_key_encrypted, balance_usd, created_at_utc, updated_at_utc FROM wallets WHERE wallet_address = ?"
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (wallet_address,))
        row = cursor.fetchone()
        if row:
            return Wallet(
                id=row[0],
                user_id=row[1],
                wallet_address=row[2],
                private_key_encrypted=row[3],
                balance_usd=row[4],
                created_at_utc=row[5],
                updated_at_utc=row[6],
            )
        return None
    finally:
        cursor.close()


def update_wallet_balance(
    conn,
    wallet_id: int,
    new_balance: float,
    busy_retries: int,
    busy_sleep_secs: float,
) -> None:
    now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    sql = "UPDATE wallets SET balance_usd = ?, updated_at_utc = ? WHERE id = ?"
    sql_execute_with_retry(
        conn, sql, (new_balance, now, wallet_id), busy_retries, busy_sleep_secs
    )


def create_transaction(
    conn,
    wallet_id: int,
    transaction_type: str,
    amount: float,
    currency: str,
    fee: float,
    status: str,
    transaction_hash: Optional[str],
    busy_retries: int,
    busy_sleep_secs: float,
) -> WalletTransaction:
    now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    sql = """
    INSERT INTO wallet_transactions (wallet_id, transaction_type, amount, currency, fee, status, transaction_hash, created_at_utc)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    RETURNING id, wallet_id, transaction_type, amount, currency, fee, status, transaction_hash, created_at_utc;
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            sql,
            (
                wallet_id,
                transaction_type,
                amount,
                currency,
                fee,
                status,
                transaction_hash,
                now,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return WalletTransaction(
            id=row[0],
            wallet_id=row[1],
            transaction_type=row[2],
            amount=row[3],
            currency=row[4],
            fee=row[5],
            status=row[6],
            transaction_hash=row[7],
            created_at_utc=row[8],
        )
    finally:
        cursor.close()


def get_wallet_transactions(
    conn, wallet_id: int, busy_retries: int, busy_sleep_secs: float
) -> List[WalletTransaction]:
    sql = """
    SELECT id, wallet_id, transaction_type, amount, currency, fee, status, transaction_hash, created_at_utc
    FROM wallet_transactions WHERE wallet_id = ? ORDER BY created_at_utc DESC
    """
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (wallet_id,))
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
                transaction_hash=row[7],
                created_at_utc=row[8],
            )
            for row in rows
        ]
    finally:
        cursor.close()


def create_trading_position(
    conn,
    wallet_id: int,
    token: str,
    position_type: str,
    entry_price: float,
    quantity: float,
    leverage: Optional[float],
    stop_loss: Optional[float],
    take_profit: Optional[float],
    busy_retries: int,
    busy_sleep_secs: float,
) -> TradingPosition:
    now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    sql = """
    INSERT INTO trading_positions (wallet_id, token, position_type, entry_price, quantity, leverage, stop_loss, take_profit, status, pnl, opened_at_utc)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', 0, ?)
    RETURNING id, wallet_id, token, position_type, entry_price, quantity, leverage, stop_loss, take_profit, status, pnl, opened_at_utc, closed_at_utc;
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            sql,
            (
                wallet_id,
                token,
                position_type,
                entry_price,
                quantity,
                leverage,
                stop_loss,
                take_profit,
                now,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
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
            pnl=row[10],
            opened_at_utc=row[11],
            closed_at_utc=row[12],
        )
    finally:
        cursor.close()


def close_trading_position(
    conn,
    position_id: int,
    pnl: float,
    busy_retries: int,
    busy_sleep_secs: float,
) -> None:
    now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    sql = """
    UPDATE trading_positions
    SET status = 'closed', pnl = ?, closed_at_utc = ?
    WHERE id = ?
    """
    sql_execute_with_retry(
        conn, sql, (pnl, now, position_id), busy_retries, busy_sleep_secs
    )


def get_open_positions(
    conn, wallet_id: int, busy_retries: int, busy_sleep_secs: float
) -> List[TradingPosition]:
    sql = """
    SELECT id, wallet_id, token, position_type, entry_price, quantity, leverage, stop_loss, take_profit, status, pnl, opened_at_utc, closed_at_utc
    FROM trading_positions WHERE wallet_id = ? AND status = 'open'
    """
    cursor = conn.cursor()
    try:
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
                pnl=row[10],
                opened_at_utc=row[11],
                closed_at_utc=row[12],
            )
            for row in rows
        ]
    finally:
        cursor.close()
