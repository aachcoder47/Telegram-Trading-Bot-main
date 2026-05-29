"""
User management system for the trading bot
Handles user registration, authentication, and wallet management
"""

import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path
import json
import sqlite3

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash


logger = logging.getLogger(__name__)
ph = PasswordHasher()


@dataclass
class User:
    """User account"""
    user_id: str
    username: str
    email: str
    password_hash: str  # Argon2 hash
    wallet_id: str  # Reference to multi-coin wallet
    deposit_address: Dict[str, str]  # coin -> address mapping
    total_deposit_usd: float = 0.0
    total_balance_usd: float = 0.0
    total_profit_usd: float = 0.0
    fees_paid_usd: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_login: Optional[str] = None
    is_active: bool = True


class UserManager:
    """Manages user accounts"""
    
    def __init__(self, db_path: str = "./tg_users.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize user database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    wallet_id TEXT NOT NULL,
                    deposit_address TEXT NOT NULL,
                    total_deposit_usd REAL DEFAULT 0.0,
                    total_balance_usd REAL DEFAULT 0.0,
                    total_profit_usd REAL DEFAULT 0.0,
                    fees_paid_usd REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deposits (
                    deposit_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    amount REAL NOT NULL,
                    tx_hash TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    confirmed_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    position_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL,
                    take_profit REAL,
                    leverage REAL,
                    quantity REAL NOT NULL,
                    status TEXT DEFAULT 'open',
                    pnl_usd REAL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"User database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize user database: {e}")
            raise
    
    def create_user(
        self,
        user_id: str,
        username: str,
        email: str,
        password: str,
        wallet_id: str,
        deposit_address: Dict[str, str]
    ) -> User:
        """Create a new user account"""
        try:
            password_hash = ph.hash(password)
            
            user = User(
                user_id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                wallet_id=wallet_id,
                deposit_address=deposit_address
            )
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (
                    user_id, username, email, password_hash, wallet_id,
                    deposit_address, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user.user_id,
                user.username,
                user.email,
                user.password_hash,
                user.wallet_id,
                json.dumps(user.deposit_address),
                user.created_at
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"User created: {username} ({user_id})")
            return user
            
        except sqlite3.IntegrityError as e:
            logger.error(f"User creation failed - duplicate username or email: {e}")
            raise ValueError("Username or email already exists")
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM users WHERE username = ?
            """, (username,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                logger.warning(f"Login attempt for nonexistent user: {username}")
                return None
            
            user = self._row_to_user(row)
            
            try:
                ph.verify(user.password_hash, password)
                logger.info(f"User authenticated: {username}")
                self._update_last_login(user.user_id)
                return user
            except (VerifyMismatchError, InvalidHash):
                logger.warning(f"Failed authentication attempt for user: {username}")
                return None
                
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return None
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            return self._row_to_user(row) if row else None
            
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            return None
    
    def update_balance(self, user_id: str, total_balance_usd: float, total_profit_usd: float):
        """Update user balance and profit"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE users SET total_balance_usd = ?, total_profit_usd = ?
                WHERE user_id = ?
            """, (total_balance_usd, total_profit_usd, user_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update user balance: {e}")
            raise
    
    def record_deposit(
        self,
        deposit_id: str,
        user_id: str,
        coin: str,
        amount: float,
        tx_hash: str = None
    ):
        """Record a deposit transaction"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO deposits (deposit_id, user_id, coin, amount, tx_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                deposit_id,
                user_id,
                coin,
                amount,
                tx_hash,
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Deposit recorded for user {user_id}: {amount} {coin}")
            
        except Exception as e:
            logger.error(f"Failed to record deposit: {e}")
            raise
    
    def confirm_deposit(self, deposit_id: str):
        """Confirm a deposit"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE deposits SET status = 'confirmed', confirmed_at = ?
                WHERE deposit_id = ?
            """, (datetime.utcnow().isoformat(), deposit_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to confirm deposit: {e}")
            raise
    
    def record_trade(
        self,
        trade_id: str,
        user_id: str,
        symbol: str,
        position_type: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        leverage: float,
        quantity: float
    ):
        """Record a trade"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO trades (
                    trade_id, user_id, symbol, position_type, entry_price,
                    stop_loss, take_profit, leverage, quantity, opened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                user_id,
                symbol,
                position_type,
                entry_price,
                stop_loss,
                take_profit,
                leverage,
                quantity,
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Trade recorded for user {user_id}: {symbol} {position_type}")
            
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
            raise
    
    def close_trade(self, trade_id: str, pnl_usd: float, fee_usd: float = 0):
        """Close a trade"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT user_id FROM trades WHERE trade_id = ?
            """, (trade_id,))
            
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Trade not found: {trade_id}")
            
            user_id = row[0]
            
            # Update trade status
            cursor.execute("""
                UPDATE trades SET status = 'closed', pnl_usd = ?, closed_at = ?
                WHERE trade_id = ?
            """, (pnl_usd, datetime.utcnow().isoformat(), trade_id))
            
            # Update fees paid
            cursor.execute("""
                UPDATE users SET fees_paid_usd = fees_paid_usd + ?
                WHERE user_id = ?
            """, (fee_usd, user_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Trade closed for user {user_id}: PnL ${pnl_usd:.2f}, Fee ${fee_usd:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to close trade: {e}")
            raise
    
    def _row_to_user(self, row) -> User:
        """Convert database row to User object"""
        return User(
            user_id=row[0],
            username=row[1],
            email=row[2],
            password_hash=row[3],
            wallet_id=row[4],
            deposit_address=json.loads(row[5]),
            total_deposit_usd=row[6],
            total_balance_usd=row[7],
            total_profit_usd=row[8],
            fees_paid_usd=row[9],
            created_at=row[10],
            last_login=row[11],
            is_active=bool(row[12])
        )
    
    def _update_last_login(self, user_id: str):
        """Update user's last login timestamp"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE users SET last_login = ? WHERE user_id = ?
            """, (datetime.utcnow().isoformat(), user_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update last login: {e}")
