import logging
from typing import Optional
from eth_account import Account
from eth_account.messages import encode_defunct
import secrets

from internal.repositories.wallets import (
    Wallet,
    WalletTransaction,
    create_wallet,
    get_wallet_by_chat_id,
    get_wallet_by_address,
    update_wallet_balance,
    create_transaction,
    get_wallet_transactions,
)
from configs.config import Config

logger = logging.getLogger(__name__)


class WalletService:
    def __init__(self, cfg: Config, db_conn):
        self.cfg = cfg
        self.db_conn = db_conn
        self.fee_percentage = 7.5  # 7.5% fee on payouts

    def generate_wallet(self) -> tuple[str, str]:
        """Generate a new Ethereum wallet address and private key"""
        private_key = secrets.token_hex(32)
        private_key_bytes = bytes.fromhex(private_key)
        account = Account.from_key(private_key_bytes)
        return account.address, private_key

    def encrypt_private_key(self, private_key: str) -> str:
        """Encrypt private key (simplified - in production use proper encryption)"""
        # In production, use proper encryption like AES with a master key
        # For now, we'll use a simple encoding
        import base64
        return base64.b64encode(private_key.encode()).decode()

    def decrypt_private_key(self, encrypted_key: str) -> str:
        """Decrypt private key (simplified - in production use proper decryption)"""
        import base64
        return base64.b64decode(encrypted_key.encode()).decode()

    def create_user_wallet(self, chat_id: int) -> Wallet:
        """Create a new wallet for a chat"""
        # Check if chat already has a wallet
        existing_wallet = get_wallet_by_chat_id(
            self.db_conn, chat_id, self.cfg.sql_busy_retries, self.cfg.sql_busy_sleep
        )
        if existing_wallet:
            logger.info(f"Chat {chat_id} already has a wallet: {existing_wallet.wallet_address}")
            return existing_wallet

        # Generate new wallet
        wallet_address, private_key = self.generate_wallet()
        encrypted_key = self.encrypt_private_key(private_key)

        # Save to database
        wallet = create_wallet(
            self.db_conn,
            chat_id,
            wallet_address,
            encrypted_key,
            self.cfg.sql_busy_retries,
            self.cfg.sql_busy_sleep,
        )

        logger.info(f"Created new wallet for chat {chat_id}: {wallet_address}")
        return wallet

    def get_user_wallet(self, chat_id: int) -> Optional[Wallet]:
        """Get chat's wallet"""
        return get_wallet_by_chat_id(
            self.db_conn, chat_id, self.cfg.sql_busy_retries, self.cfg.sql_busy_sleep
        )

    def deposit_to_wallet(self, chat_id: int, amount: float, currency: str = "USDT") -> WalletTransaction:
        """Deposit funds to chat's wallet"""
        wallet = self.get_user_wallet(chat_id)
        if not wallet:
            raise ValueError(f"No wallet found for chat {chat_id}")

        # Update wallet balance
        new_balance = wallet.balance_usd + amount
        update_wallet_balance(
            self.db_conn,
            wallet.id,
            new_balance,
            self.cfg.sql_busy_retries,
            self.cfg.sql_busy_sleep,
        )

        # Create transaction record
        transaction = create_transaction(
            self.db_conn,
            wallet.id,
            "deposit",
            amount,
            currency,
            0,  # No fee on deposits
            "completed",
            None,
            self.cfg.sql_busy_retries,
            self.cfg.sql_busy_sleep,
        )

        logger.info(f"Deposited {amount} {currency} to wallet {wallet.wallet_address}")
        return transaction

    def withdraw_from_wallet(self, chat_id: int, amount: float, currency: str = "USDT") -> WalletTransaction:
        """Withdraw funds from chat's wallet with 7.5% fee"""
        wallet = self.get_user_wallet(chat_id)
        if not wallet:
            raise ValueError(f"No wallet found for chat {chat_id}")

        # Calculate fee (7.5%)
        fee = amount * (self.fee_percentage / 100)
        total_deduction = amount + fee

        # Check if wallet has sufficient balance
        if wallet.balance_usd < total_deduction:
            raise ValueError(f"Insufficient balance. Available: {wallet.balance_usd}, Required: {total_deduction}")

        # Update wallet balance
        new_balance = wallet.balance_usd - total_deduction
        update_wallet_balance(
            self.db_conn,
            wallet.id,
            new_balance,
            self.cfg.sql_busy_retries,
            self.cfg.sql_busy_sleep,
        )

        # Create transaction record for withdrawal
        withdrawal_tx = create_transaction(
            self.db_conn,
            wallet.id,
            "withdraw",
            amount,
            currency,
            fee,
            "completed",
            None,
            self.cfg.sql_busy_retries,
            self.cfg.sql_busy_sleep,
        )

        # Create fee transaction record
        fee_tx = create_transaction(
            self.db_conn,
            wallet.id,
            "fee",
            fee,
            currency,
            0,
            "completed",
            None,
            self.cfg.sql_busy_retries,
            self.cfg.sql_busy_sleep,
        )

        logger.info(f"Withdrew {amount} {currency} from wallet {wallet.wallet_address} with {fee} {currency} fee (7.5%)")
        return withdrawal_tx

    def get_wallet_balance(self, chat_id: int) -> float:
        """Get chat's wallet balance"""
        wallet = self.get_user_wallet(chat_id)
        if not wallet:
            return 0.0
        return wallet.balance_usd

    def get_transaction_history(self, chat_id: int) -> list[WalletTransaction]:
        """Get chat's transaction history"""
        wallet = self.get_user_wallet(chat_id)
        if not wallet:
            return []
        return get_wallet_transactions(
            self.db_conn, wallet.id, self.cfg.sql_busy_retries, self.cfg.sql_busy_sleep
        )

    def deduct_for_trade(self, chat_id: int, amount: float) -> bool:
        """Deduct funds from wallet for trading"""
        wallet = self.get_user_wallet(chat_id)
        if not wallet:
            raise ValueError(f"No wallet found for chat {chat_id}")

        if wallet.balance_usd < amount:
            return False

        new_balance = wallet.balance_usd - amount
        update_wallet_balance(
            self.db_conn,
            wallet.id,
            new_balance,
            self.cfg.sql_busy_retries,
            self.cfg.sql_busy_sleep,
        )

        # Create transaction record
        create_transaction(
            self.db_conn,
            wallet.id,
            "trade",
            amount,
            "USDT",
            0,
            "completed",
            None,
            self.cfg.sql_busy_retries,
            self.cfg.sql_busy_sleep,
        )

        return True

    def add_trade_pnl(self, chat_id: int, pnl: float) -> None:
        """Add PnL from trade to wallet"""
        wallet = self.get_user_wallet(chat_id)
        if not wallet:
            raise ValueError(f"No wallet found for chat {chat_id}")

        new_balance = wallet.balance_usd + pnl
        update_wallet_balance(
            self.db_conn,
            wallet.id,
            new_balance,
            self.cfg.sql_busy_retries,
            self.cfg.sql_busy_sleep,
        )

        # Create transaction record
        create_transaction(
            self.db_conn,
            wallet.id,
            "trade",
            pnl,
            "USDT",
            0,
            "completed",
            None,
            self.cfg.sql_busy_retries,
            self.cfg.sql_busy_sleep,
        )

        logger.info(f"Added PnL of {pnl} USDT to wallet {wallet.wallet_address}")
