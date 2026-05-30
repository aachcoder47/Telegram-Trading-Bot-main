"""
Automated trading executor
Executes trades based on AI signal, manages positions, and handles profit/fee transfers
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Any
import json

import ccxt


logger = logging.getLogger(__name__)


@dataclass
class TradeExecution:
    """Result of a trade execution"""
    trade_id: str
    status: str  # 'pending', 'open', 'closed'
    symbol: str
    position_type: str
    entry_price: float
    quantity: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    leverage: Optional[float]
    opened_at: str
    current_price: Optional[float] = None
    pnl_usd: Optional[float] = None
    closed_at: Optional[str] = None


class TradingExecutor:
    """Executes trades using CCXT exchange API"""
    
    def __init__(
        self,
        exchange_name: str,
        api_key: str,
        api_secret: str,
        password: Optional[str] = None,
        sandbox: bool = False,
        fee_wallet_address: Optional[str] = None,
        fee_percentage: float = 5.0
    ):
        """
        Initialize trading executor
        exchange_name: 'binance', 'bitunix', 'xt', etc.
        """
        self.exchange_name = exchange_name.lower()
        self.sandbox = sandbox
        self.fee_wallet_address = fee_wallet_address
        self.fee_percentage = fee_percentage
        
        # Initialize exchange connection
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            self.exchange = exchange_class({
                'apiKey': api_key,
                'secret': api_secret,
                'password': password,
                'sandbox': sandbox,
                'enableRateLimit': True,
            })
            logger.info(f"Trading executor initialized for {self.exchange_name}")
        except Exception as e:
            logger.error(f"Failed to initialize {self.exchange_name}: {e}")
            raise
    
    def get_balance(self) -> Dict[str, float]:
        """Get user's account balance"""
        try:
            balance = self.exchange.fetch_balance()
            return {
                symbol: balance.get(symbol, {}).get('free', 0)
                for symbol in balance.get('free', {})
            }
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return {}
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get current ticker for symbol"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "last": ticker.get("last"),
                "timestamp": ticker.get("timestamp")
            }
        except Exception as e:
            logger.warning(f"Failed to fetch ticker for {symbol}: {e}")
            return None
    
    def execute_trade(
        self,
        user_id: str,
        symbol: str,
        position_type: str,  # 'long' or 'short'
        entry_price: float,
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        leverage: Optional[float] = None
    ) -> Optional[TradeExecution]:
        """
        Execute a trade (buy/sell) on the exchange
        """
        try:
            trade_id = f"trade_{uuid.uuid4().hex[:12]}"
            
            logger.info(
                f"Executing {position_type} trade for user {user_id}: "
                f"{quantity} {symbol} @ ${entry_price}"
            )
            
            # Determine order type: long = buy, short = sell
            order_side = 'buy' if position_type == 'long' else 'sell'
            
            # Place market order
            order = self.exchange.create_market_order(
                symbol,
                order_side,
                quantity
            )
            
            # Create trade execution record
            execution = TradeExecution(
                trade_id=trade_id,
                status='open',
                symbol=symbol,
                position_type=position_type,
                entry_price=entry_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=leverage,
                opened_at=datetime.utcnow().isoformat(),
                current_price=float(order.get("average", entry_price))
            )
            
            logger.info(f"Trade opened: {trade_id} - {order}")
            
            # TODO: Set stop loss and take profit orders if supported by exchange
            if stop_loss and self.exchange.has['createOrder']:
                try:
                    self.exchange.create_order(
                        symbol,
                        'limit',
                        'sell' if position_type == 'long' else 'buy',
                        quantity,
                        stop_loss,
                        {'stopPrice': stop_loss}
                    )
                    logger.info(f"Stop loss set at ${stop_loss} for {trade_id}")
                except Exception as e:
                    logger.warning(f"Failed to set stop loss: {e}")
            
            if take_profit and self.exchange.has['createOrder']:
                try:
                    self.exchange.create_order(
                        symbol,
                        'limit',
                        'sell' if position_type == 'long' else 'buy',
                        quantity,
                        take_profit
                    )
                    logger.info(f"Take profit set at ${take_profit} for {trade_id}")
                except Exception as e:
                    logger.warning(f"Failed to set take profit: {e}")
            
            return execution
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return None
    
    def close_trade(
        self,
        trade_id: str,
        symbol: str,
        quantity: float,
        position_type: str,
        exit_price: float
    ) -> Optional[Dict]:
        """
        Close a trade and return P&L
        """
        try:
            # Determine exit side: opposite of entry
            exit_side = 'sell' if position_type == 'long' else 'buy'
            
            # Close position
            order = self.exchange.create_market_order(
                symbol,
                exit_side,
                quantity
            )
            
            actual_exit_price = float(order.get("average", exit_price))
            
            # Calculate P&L
            if position_type == 'long':
                pnl_per_unit = actual_exit_price - exit_price
            else:  # short
                pnl_per_unit = exit_price - actual_exit_price
            
            pnl_usd = pnl_per_unit * quantity
            
            logger.info(f"Trade closed: {trade_id} - P&L: ${pnl_usd:.2f}")
            
            return {
                "trade_id": trade_id,
                "status": "closed",
                "exit_price": actual_exit_price,
                "pnl_usd": pnl_usd,
                "closed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to close trade {trade_id}: {e}")
            return None
    
    def calculate_fee_transfer(
        self,
        pnl_usd: float
    ) -> tuple[float, float]:
        """
        Calculate fee transfer to owner wallet
        Returns: (fee_amount_usd, user_payout_usd)
        """
        fee_amount = pnl_usd * (self.fee_percentage / 100)
        user_payout = pnl_usd - fee_amount
        
        logger.info(
            f"P&L breakdown - Total: ${pnl_usd:.2f}, "
            f"Fee ({self.fee_percentage}%): ${fee_amount:.2f}, "
            f"User payout: ${user_payout:.2f}"
        )
        
        return fee_amount, user_payout
    
    def process_profit_transfer(
        self,
        user_id: str,
        pnl_usd: float,
        user_manager
    ) -> Dict:
        """
        Process profit distribution: deduct fee and update user balance
        """
        try:
            fee_amount, user_payout = self.calculate_fee_transfer(pnl_usd)
            
            # Update user's balance and fees paid
            user = user_manager.get_user(user_id)
            if user:
                new_balance = user.total_balance_usd + user_payout
                new_profit = user.total_profit_usd + user_payout
                new_fees_paid = user.fees_paid_usd + fee_amount
                
                user_manager.update_balance(user_id, new_balance, new_profit)
                
                logger.info(
                    f"Profit processed for user {user_id}: "
                    f"P&L=${pnl_usd:.2f}, Fee=${fee_amount:.2f}, "
                    f"Payout=${user_payout:.2f}"
                )
                
                return {
                    "user_id": user_id,
                    "total_pnl": pnl_usd,
                    "fee_deducted": fee_amount,
                    "user_payout": user_payout,
                    "new_balance": new_balance,
                    "fee_wallet_address": self.fee_wallet_address
                }
            
            return {"error": "User not found"}
            
        except Exception as e:
            logger.error(f"Failed to process profit transfer for user {user_id}: {e}")
            return {"error": str(e)}
