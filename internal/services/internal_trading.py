import logging
import random
from typing import Optional, Dict, Any
from datetime import datetime

from internal.repositories.wallets import (
    TradingPosition,
    create_trading_position,
    close_trading_position,
    get_open_positions,
)
from internal.services.wallet_service import WalletService
from configs.config import Config

logger = logging.getLogger(__name__)


class InternalTradingService:
    """Internal trading system that simulates trades without external exchanges"""

    def __init__(self, cfg: Config, db_conn, wallet_service: WalletService):
        self.cfg = cfg
        self.db_conn = db_conn
        self.wallet_service = wallet_service

    def get_simulated_price(self, token: str) -> float:
        """Get simulated price for a token (in production, this would use real price feeds)"""
        # Simulated prices for common tokens
        price_map = {
            "BTC": 45000.0,
            "ETH": 3000.0,
            "USDT": 1.0,
            "USDC": 1.0,
            "BNB": 400.0,
            "SOL": 100.0,
            "XRP": 0.5,
            "ADA": 0.5,
            "DOGE": 0.1,
            "MATIC": 0.8,
        }
        
        base_price = price_map.get(token.upper(), 1.0)
        # Add some randomness to simulate price movement
        variation = random.uniform(-0.02, 0.02)  # ±2% variation
        return base_price * (1 + variation)

    def execute_trade(
        self,
        chat_id: int,
        token: str,
        position_type: str,  # 'long' or 'short'
        entry_price: Optional[float],
        quantity: float,
        leverage: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute a trade internally"""
        try:
            # Get chat's wallet
            wallet = self.wallet_service.get_user_wallet(chat_id)
            if not wallet:
                return {"success": False, "error": "No wallet found for chat"}

            # Get current price if not provided
            if entry_price is None:
                entry_price = self.get_simulated_price(token)

            # Calculate trade value
            trade_value = entry_price * quantity
            if leverage:
                trade_value = trade_value / leverage

            # Check if wallet has sufficient balance
            if wallet.balance_usd < trade_value:
                return {"success": False, "error": f"Insufficient balance. Required: {trade_value}, Available: {wallet.balance_usd}"}

            # Deduct funds from wallet
            if not self.wallet_service.deduct_for_trade(chat_id, trade_value):
                return {"success": False, "error": "Failed to deduct funds from wallet"}

            # Create trading position
            position = create_trading_position(
                self.db_conn,
                wallet.id,
                token.upper(),
                position_type.lower(),
                entry_price,
                quantity,
                leverage,
                stop_loss,
                take_profit,
                self.cfg.sql_busy_retries,
                self.cfg.sql_busy_sleep,
            )

            logger.info(
                f"Executed {position_type} trade for chat {chat_id}: {quantity} {token} @ {entry_price}"
            )

            return {
                "success": True,
                "position_id": position.id,
                "token": position.token,
                "position_type": position.position_type,
                "entry_price": position.entry_price,
                "quantity": position.quantity,
                "leverage": position.leverage,
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "trade_value": trade_value,
            }

        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return {"success": False, "error": str(e)}

    def close_position(
        self,
        chat_id: int,
        position_id: int,
        exit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Close a trading position"""
        try:
            # Get chat's wallet
            wallet = self.wallet_service.get_user_wallet(chat_id)
            if not wallet:
                return {"success": False, "error": "No wallet found for chat"}

            # Get open positions
            open_positions = get_open_positions(
                self.db_conn, wallet.id, self.cfg.sql_busy_retries, self.cfg.sql_busy_sleep
            )
            
            position = None
            for pos in open_positions:
                if pos.id == position_id:
                    position = pos
                    break
            
            if not position:
                return {"success": False, "error": "Position not found or already closed"}

            # Get exit price if not provided
            if exit_price is None:
                exit_price = self.get_simulated_price(position.token)

            # Calculate PnL
            if position.position_type == "long":
                pnl = (exit_price - position.entry_price) * position.quantity
            else:  # short
                pnl = (position.entry_price - exit_price) * position.quantity

            # Apply leverage if applicable
            if position.leverage:
                pnl = pnl * position.leverage

            # Close the position
            close_trading_position(
                self.db_conn,
                position_id,
                pnl,
                self.cfg.sql_busy_retries,
                self.cfg.sql_busy_sleep,
            )

            # Add PnL to wallet
            self.wallet_service.add_trade_pnl(chat_id, pnl)

            logger.info(
                f"Closed position {position_id} for chat {chat_id}: PnL = {pnl} USDT"
            )

            return {
                "success": True,
                "position_id": position_id,
                "exit_price": exit_price,
                "pnl": pnl,
                "token": position.token,
            }

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {"success": False, "error": str(e)}

    def get_user_positions(self, chat_id: int) -> list[TradingPosition]:
        """Get all open positions for a chat"""
        wallet = self.wallet_service.get_user_wallet(chat_id)
        if not wallet:
            return []
        
        return get_open_positions(
            self.db_conn, wallet.id, self.cfg.sql_busy_retries, self.cfg.sql_busy_sleep
        )

    def auto_trade_with_ai_signal(
        self,
        chat_id: int,
        ai_signal: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute trade based on AI signal"""
        token = ai_signal.get("token")
        position_type = ai_signal.get("position_type")
        entry_price = ai_signal.get("entry_price")
        leverage = ai_signal.get("leverage", 2)  # Default 2x leverage
        stop_losses = ai_signal.get("stop_losses", [])
        take_profits = ai_signal.get("take_profits", [])

        if not token or not position_type:
            return {"success": False, "error": "Invalid AI signal: missing token or position_type"}

        # Calculate quantity based on wallet balance and leverage
        wallet_balance = self.wallet_service.get_wallet_balance(chat_id)
        if wallet_balance <= 0:
            return {"success": False, "error": "Insufficient wallet balance"}

        # Use 10% of wallet balance per trade
        trade_amount = wallet_balance * 0.10
        if entry_price:
            quantity = trade_amount / entry_price
        else:
            quantity = trade_amount / self.get_simulated_price(token)

        # Get stop loss and take profit
        stop_loss = stop_losses[0] if stop_losses else None
        take_profit = take_profits[0] if take_profits else None

        # Execute the trade
        return self.execute_trade(
            chat_id=chat_id,
            token=token,
            position_type=position_type,
            entry_price=entry_price,
            quantity=quantity,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
