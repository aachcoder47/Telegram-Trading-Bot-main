"""
Multi-coin wallet management system
Supports BTC, ETH, and other major cryptocurrencies
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, Optional, List
from pathlib import Path
import secrets
import hashlib

from web3 import Web3
from bitcoinlib.mnemonic import Mnemonic
from bitcoinlib.keys import HDKey


logger = logging.getLogger(__name__)


@dataclass
class WalletAddress:
    """Represents a wallet address for a specific coin"""
    coin: str  # 'BTC', 'ETH', 'USDT', etc.
    address: str
    public_key: Optional[str] = None
    derivation_path: Optional[str] = None


@dataclass
class UserWallet:
    """User's multi-coin wallet"""
    user_id: str
    wallet_id: str
    mnemonic: str  # encrypted
    addresses: Dict[str, WalletAddress]  # coin -> address
    created_at: str
    balance: Dict[str, float] = None  # coin -> balance
    
    def __post_init__(self):
        if self.balance is None:
            self.balance = {}


class WalletManager:
    """Manages multi-coin wallet generation and management"""
    
    def __init__(self, wallet_data_dir: Path = None):
        self.wallet_data_dir = wallet_data_dir or Path("./output/wallets")
        self.wallet_data_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_mnemonic(self, strength: int = 256) -> str:
        """Generate a BIP39 mnemonic phrase"""
        mnemo = Mnemonic('english')
        mnemonic = mnemo.generate(strength=strength)
        return mnemonic
    
    def generate_btc_address(self, mnemonic: str, account: int = 0) -> WalletAddress:
        """Generate Bitcoin address from mnemonic (BIP44)"""
        try:
            hdkey = HDKey.from_mnemonic(mnemonic)
            # BIP44 path: m/44'/0'/0'/0/0 (Bitcoin mainnet)
            derivation_path = f"m/44'/0'/{account}'/0/0"
            key = hdkey.subkey_for_path(derivation_path)
            address = key.address()
            
            return WalletAddress(
                coin="BTC",
                address=address,
                public_key=key.public_hex(),
                derivation_path=derivation_path
            )
        except Exception as e:
            logger.error(f"Failed to generate Bitcoin address: {e}")
            raise
    
    def generate_eth_address(self, mnemonic: str, account: int = 0) -> WalletAddress:
        """Generate Ethereum address from mnemonic (BIP44)"""
        try:
            hdkey = HDKey.from_mnemonic(mnemonic)
            # BIP44 path: m/44'/60'/0'/0/0 (Ethereum mainnet)
            derivation_path = f"m/44'/60'/{account}'/0/0"
            key = hdkey.subkey_for_path(derivation_path)
            
            # Convert to Ethereum format
            private_key_bytes = bytes.fromhex(key.private_hex())
            account_obj = Web3.eth.account.from_key(private_key_bytes)
            
            return WalletAddress(
                coin="ETH",
                address=account_obj.address,
                public_key=account_obj.key.hex(),
                derivation_path=derivation_path
            )
        except Exception as e:
            logger.error(f"Failed to generate Ethereum address: {e}")
            raise
    
    def generate_multi_coin_wallet(self, user_id: str) -> UserWallet:
        """Generate a new multi-coin wallet for user"""
        try:
            mnemonic = self.generate_mnemonic()
            wallet_id = secrets.token_hex(16)
            
            addresses = {}
            
            # Generate Bitcoin address
            btc_addr = self.generate_btc_address(mnemonic)
            addresses[btc_addr.coin] = btc_addr
            
            # Generate Ethereum address
            eth_addr = self.generate_eth_address(mnemonic)
            addresses[eth_addr.coin] = eth_addr
            
            # TODO: Add more coins as needed (USDT on different chains, etc.)
            
            wallet = UserWallet(
                user_id=user_id,
                wallet_id=wallet_id,
                mnemonic=mnemonic,  # In production, encrypt this!
                addresses=addresses,
                created_at=str(Path(__file__).parent)  # Will be set to datetime
            )
            
            logger.info(f"Generated wallet {wallet_id} for user {user_id}")
            return wallet
        except Exception as e:
            logger.error(f"Failed to generate wallet: {e}")
            raise
    
    def save_wallet(self, wallet: UserWallet):
        """Save wallet to secure storage"""
        try:
            wallet_file = self.wallet_data_dir / f"{wallet.user_id}_{wallet.wallet_id}.json"
            
            wallet_data = {
                "user_id": wallet.user_id,
                "wallet_id": wallet.wallet_id,
                "mnemonic": wallet.mnemonic,  # TODO: Encrypt before saving!
                "addresses": {
                    coin: {
                        "coin": addr.coin,
                        "address": addr.address,
                        "public_key": addr.public_key,
                        "derivation_path": addr.derivation_path
                    }
                    for coin, addr in wallet.addresses.items()
                },
                "created_at": wallet.created_at,
                "balance": wallet.balance
            }
            
            wallet_file.write_text(json.dumps(wallet_data, indent=2))
            logger.info(f"Wallet saved to {wallet_file}")
            
        except Exception as e:
            logger.error(f"Failed to save wallet: {e}")
            raise
    
    def load_wallet(self, user_id: str, wallet_id: str) -> Optional[UserWallet]:
        """Load wallet from storage"""
        try:
            wallet_file = self.wallet_data_dir / f"{user_id}_{wallet_id}.json"
            
            if not wallet_file.exists():
                logger.warning(f"Wallet file not found: {wallet_file}")
                return None
            
            data = json.loads(wallet_file.read_text())
            
            addresses = {}
            for coin, addr_data in data.get("addresses", {}).items():
                addresses[coin] = WalletAddress(
                    coin=addr_data["coin"],
                    address=addr_data["address"],
                    public_key=addr_data.get("public_key"),
                    derivation_path=addr_data.get("derivation_path")
                )
            
            wallet = UserWallet(
                user_id=data["user_id"],
                wallet_id=data["wallet_id"],
                mnemonic=data["mnemonic"],  # TODO: Decrypt
                addresses=addresses,
                created_at=data["created_at"],
                balance=data.get("balance", {})
            )
            
            logger.info(f"Loaded wallet {wallet_id} for user {user_id}")
            return wallet
            
        except Exception as e:
            logger.error(f"Failed to load wallet: {e}")
            return None
    
    def get_wallet_addresses_by_coin(self, wallet: UserWallet, coin: str) -> Optional[str]:
        """Get wallet address for a specific coin"""
        addr = wallet.addresses.get(coin)
        return addr.address if addr else None
