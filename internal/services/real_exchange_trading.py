import logging
import ccxt
from typing import Optional, Dict, Any, List
from configs.config import Config
from internal.repositories.wallets import (
    TradingPosition,
    create_trading_position,
    get_open_positions,
    close_trading_position,
)
from internal.services.wallet_service import WalletService

logger = logging.getLogger(__name__)


class RealExchangeTradingService:
    """Service for real trading on cryptocurrency exchanges"""
    
    def __init__(self, db_conn, cfg: Config, wallet_service: WalletService):
        self.db_conn = db_conn
        self.cfg = cfg
        self.wallet_service = wallet_service
        self.exchange = self._init_exchange()
    
    def _init_exchange(self) -> ccxt.Exchange:
        """Initialize exchange connection"""
        try:
            if self.cfg.exchange == 'binance':
                exchange = ccxt.binance({
                    'apiKey': self.cfg.binance_api_key,
                    'secret': self.cfg.binance_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'future',  # Use futures for leverage trading
                    }
                })
            elif self.cfg.exchange == 'bybit':
                exchange = ccxt.bybit({
                    'apiKey': self.cfg.bybit_api_key,
                    'secret': self.cfg.bybit_secret,
                    'enableRateLimit': True,
                })
            else:
                raise ValueError(f"Unsupported exchange: {self.cfg.exchange}")
            
            # Test connection
            exchange.load_markets()
            logger.info(f"Connected to {self.cfg.exchange} exchange")
            return exchange
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise
    
    def get_real_price(self, symbol: str) -> float:
        """Get real-time price from exchange"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Failed to fetch price for {symbol}: {e}")
            raise
    
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
        """Execute a real trade on the exchange"""
        try:
            # Get chat's wallet
            wallet = self.wallet_service.get_user_wallet(chat_id)
            if not wallet:
                return {"success": False, "error": "No wallet found for chat"}
            
            # Format symbol for exchange (e.g., BTC/USDT)
            symbol = f"{token.upper()}/USDT"
            
            # Get real entry price if not provided
            if not entry_price:
                entry_price = self.get_real_price(symbol)
            
            # Calculate trade value
            trade_value = entry_price * quantity
            if leverage:
                trade_value = trade_value / leverage
            
            # Check if wallet has sufficient balance
            if wallet.balance_usd < trade_value:
                return {"success": False, "error": f"Insufficient balance. Required: {trade_value:.2f}, Available: {wallet.balance_usd:.2f}"}
            
            # Deduct funds from wallet
            if not self.wallet_service.deduct_for_trade(chat_id, trade_value):
                return {"success": False, "error": "Failed to deduct funds from wallet"}
            
            # Set leverage if provided
            if leverage and hasattr(self.exchange, 'set_leverage'):
                try:
                    self.exchange.set_leverage(int(leverage), symbol)
                except Exception as e:
                    logger.warning(f"Failed to set leverage: {e}")
            
            # Execute real order on exchange
            side = 'buy' if position_type.lower() == 'long' else 'sell'
            
            # Create order with stop-loss and take-profit
            order_params = {}
            if stop_loss:
                order_params['stopLoss'] = {
                    'price': stop_loss,
                    'type': 'limit',
                }
            if take_profit:
                order_params['takeProfit'] = {
                    'price': take_profit,
                    'type': 'limit',
                }
            
            # Execute market order
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=quantity,
                params=order_params
            )
            
            logger.info(f"Executed real {side} order on {self.cfg.exchange}: {order}")
            
            # Create trading position in database
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
                "exchange_order_id": order['id'],
            }
            
        except Exception as e:
            logger.error(f"Error executing real trade: {e}")
            return {"success": False, "error": str(e)}
    
    def close_position(
        self,
        chat_id: int,
        position_id: int,
        exit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Close a trading position on the exchange"""
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
            
            # Format symbol
            symbol = f"{position.token}/USDT"
            
            # Get exit price if not provided
            if not exit_price:
                exit_price = self.get_real_price(symbol)
            
            # Calculate opposite side for closing
            close_side = 'sell' if position.position_type == 'long' else 'buy'
            
            # Execute closing order on exchange
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=close_side,
                amount=position.quantity,
            )
            
            # Calculate PnL
            if position.position_type == 'long':
                pnl = (exit_price - position.entry_price) * position.quantity
            else:  # short
                pnl = (position.entry_price - exit_price) * position.quantity
            
            # Apply leverage if set
            if position.leverage:
                pnl = pnl * position.leverage
            
            # Close the position in database
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
                f"Closed position {position_id} on {self.cfg.exchange}: PnL = {pnl:.2f} USDT"
            )
            
            return {
                "success": True,
                "position_id": position_id,
                "exit_price": exit_price,
                "pnl": pnl,
                "token": position.token,
                "exchange_order_id": order['id'],
            }
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {"success": False, "error": str(e)}
    
    def get_user_positions(self, chat_id: int) -> List[TradingPosition]:
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
            quantity = trade_amount / self.get_real_price(f"{token.upper()}/USDT")
        
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
