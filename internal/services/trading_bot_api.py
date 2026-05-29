"""
REST API endpoints for trading bot
Handles user registration, authentication, wallet management, and trading
"""

import json
import logging
from typing import Dict, Any

from internal.services.signup_service import SignupService
from internal.services.user_manager import UserManager
from internal.services.wallet_manager import WalletManager
from internal.services.deposit_watcher import DepositWatcher
from internal.services.trading_executor import TradingExecutor
from configs.config import Config


logger = logging.getLogger(__name__)


class TradingBotAPI:
    """Main API handler for trading bot"""
    
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.wallet_manager = WalletManager()
        self.user_manager = UserManager(cfg.db_path)
        self.signup_service = SignupService(self.user_manager, self.wallet_manager)
        self.deposit_watcher = DepositWatcher(cfg.min_deposit_usd)
    
    def register(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """Register a new user"""
        try:
            result = self.signup_service.register_user(username, email, password)
            if result:
                return {
                    "status": "success",
                    "message": "User registered successfully",
                    "user": result
                }
            else:
                return {
                    "status": "error",
                    "message": "Registration failed"
                }
        except ValueError as e:
            return {
                "status": "error",
                "message": str(e)
            }
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return {
                "status": "error",
                "message": "Registration failed"
            }
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user"""
        try:
            user = self.user_manager.authenticate(username, password)
            if user:
                return {
                    "status": "success",
                    "message": "Login successful",
                    "user_id": user.user_id,
                    "username": user.username,
                    "deposit_addresses": user.deposit_address
                }
            else:
                return {
                    "status": "error",
                    "message": "Invalid credentials"
                }
        except Exception as e:
            logger.error(f"Login error: {e}")
            return {
                "status": "error",
                "message": "Login failed"
            }
    
    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user account information"""
        try:
            user = self.user_manager.get_user(user_id)
            if user:
                return {
                    "status": "success",
                    "user": {
                        "user_id": user.user_id,
                        "username": user.username,
                        "email": user.email,
                        "total_deposit_usd": user.total_deposit_usd,
                        "total_balance_usd": user.total_balance_usd,
                        "total_profit_usd": user.total_profit_usd,
                        "fees_paid_usd": user.fees_paid_usd,
                        "created_at": user.created_at,
                        "is_active": user.is_active
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": "User not found"
                }
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return {
                "status": "error",
                "message": "Failed to retrieve user info"
            }
    
    def get_deposit_addresses(self, user_id: str) -> Dict[str, Any]:
        """Get user's deposit addresses"""
        try:
            addresses = self.signup_service.get_user_deposit_addresses(user_id)
            if addresses:
                return {
                    "status": "success",
                    "deposit_addresses": addresses,
                    "min_required_usd": self.cfg.min_deposit_usd
                }
            else:
                return {
                    "status": "error",
                    "message": "User not found"
                }
        except Exception as e:
            logger.error(f"Error getting deposit addresses: {e}")
            return {
                "status": "error",
                "message": "Failed to retrieve addresses"
            }
    
    def check_deposit_status(
        self,
        user_id: str,
        etherscan_api_key: str = None
    ) -> Dict[str, Any]:
        """Check deposit status for user"""
        try:
            user = self.user_manager.get_user(user_id)
            if not user:
                return {
                    "status": "error",
                    "message": "User not found"
                }
            
            status = self.deposit_watcher.check_deposit_status(
                user.deposit_address,
                etherscan_api_key
            )
            
            return {
                "status": "success",
                "deposit_status": status,
                "user_id": user_id
            }
        except Exception as e:
            logger.error(f"Error checking deposit status: {e}")
            return {
                "status": "error",
                "message": "Failed to check deposit status"
            }
    
    def place_trade(
        self,
        user_id: str,
        symbol: str,
        position_type: str,
        entry_price: float,
        quantity: float,
        stop_loss: float = None,
        take_profit: float = None,
        leverage: float = None
    ) -> Dict[str, Any]:
        """Place a trade for user"""
        try:
            user = self.user_manager.get_user(user_id)
            if not user:
                return {
                    "status": "error",
                    "message": "User not found"
                }
            
            # Check minimum deposit
            if user.total_balance_usd < self.cfg.min_deposit_usd:
                return {
                    "status": "error",
                    "message": f"Insufficient deposit. Required: ${self.cfg.min_deposit_usd}, Current: ${user.total_balance_usd:.2f}"
                }
            
            # Initialize trading executor based on configured exchange
            executor = TradingExecutor(
                exchange_name=self.cfg.exchange,
                api_key=self._get_exchange_api_key(),
                api_secret=self._get_exchange_api_secret(),
                password=self._get_exchange_password(),
                fee_wallet_address=self.cfg.fee_wallet_address,
                fee_percentage=self.cfg.fee_percentage
            )
            
            # Execute trade
            trade = executor.execute_trade(
                user_id=user_id,
                symbol=symbol,
                position_type=position_type,
                entry_price=entry_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=leverage
            )
            
            if trade:
                # Record trade in database
                self.user_manager.record_trade(
                    trade_id=trade.trade_id,
                    user_id=user_id,
                    symbol=symbol,
                    position_type=position_type,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    leverage=leverage,
                    quantity=quantity
                )
                
                return {
                    "status": "success",
                    "message": "Trade placed successfully",
                    "trade": {
                        "trade_id": trade.trade_id,
                        "symbol": trade.symbol,
                        "position_type": trade.position_type,
                        "entry_price": trade.entry_price,
                        "quantity": trade.quantity,
                        "opened_at": trade.opened_at
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": "Trade execution failed"
                }
        except Exception as e:
            logger.error(f"Error placing trade: {e}")
            return {
                "status": "error",
                "message": "Trade placement failed"
            }
    
    def _get_exchange_api_key(self) -> str:
        """Get exchange API key based on configured exchange"""
        if self.cfg.exchange == "xt":
            return self.cfg.xt_api_key or ""
        elif self.cfg.exchange == "bitunix":
            return self.cfg.bitunix_api_key or ""
        return ""
    
    def _get_exchange_api_secret(self) -> str:
        """Get exchange API secret"""
        if self.cfg.exchange == "xt":
            return self.cfg.xt_secret or ""
        elif self.cfg.exchange == "bitunix":
            return self.cfg.bitunix_secret or ""
        return ""
    
    def _get_exchange_password(self) -> str:
        """Get exchange password if required"""
        if self.cfg.exchange == "xt":
            return self.cfg.xt_password or ""
        elif self.cfg.exchange == "bitunix":
            return ""
        return ""
