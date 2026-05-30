"""
User signup and onboarding service
Handles wallet generation and deposit address creation
"""

import logging
import secrets
import uuid
from typing import Optional, Dict

from internal.services.wallet_manager import WalletManager
from internal.services.user_manager import UserManager


logger = logging.getLogger(__name__)


class SignupService:
    """Manages user registration and onboarding"""
    
    def __init__(self, user_manager: UserManager, wallet_manager: WalletManager):
        self.user_manager = user_manager
        self.wallet_manager = wallet_manager
    
    def register_user(
        self,
        username: str,
        email: str,
        password: str
    ) -> Optional[Dict]:
        """
        Register a new user with multi-coin wallet
        Returns user info with deposit addresses or None on error
        """
        try:
            # Generate unique user ID
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            
            # Generate multi-coin wallet
            wallet = self.wallet_manager.generate_multi_coin_wallet(user_id)
            logger.info(f"Generated wallet for user {user_id}")
            
            # Save wallet to storage
            self.wallet_manager.save_wallet(wallet)
            
            # Extract deposit addresses by coin
            deposit_addresses = {
                coin: addr.address
                for coin, addr in wallet.addresses.items()
            }
            
            # Create user account
            user = self.user_manager.create_user(
                user_id=user_id,
                username=username,
                email=email,
                password=password,
                wallet_id=wallet.wallet_id,
                deposit_address=deposit_addresses
            )
            
            logger.info(f"User registered: {username} ({user_id})")
            
            return {
                "user_id": user.user_id,
                "username": user.username,
                "wallet_id": wallet.wallet_id,
                "deposit_addresses": {
                    coin: addr.address
                    for coin, addr in wallet.addresses.items()
                }
            }
            
        except ValueError as e:
            logger.warning(f"Signup failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Signup failed with exception: {e}")
            return None
    
    def get_user_deposit_addresses(self, user_id: str) -> Optional[Dict[str, str]]:
        """Get user's deposit addresses by coin"""
        try:
            user = self.user_manager.get_user(user_id)
            if not user:
                logger.warning(f"User not found: {user_id}")
                return None
            
            return user.deposit_address
            
        except Exception as e:
            logger.error(f"Failed to get deposit addresses: {e}")
            return None
