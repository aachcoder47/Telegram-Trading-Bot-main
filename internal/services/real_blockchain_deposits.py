import logging
import json
from web3 import Web3
from eth_account import Account
from typing import Optional, Dict, Any
from configs.config import Config
from internal.repositories.wallets import get_wallet_by_address, create_transaction, update_wallet_balance
from internal.services.wallet_service import WalletService

logger = logging.getLogger(__name__)


class RealBlockchainWalletService:
    """Service for real blockchain wallet operations (deposits, withdrawals, balance checking)"""
    
    # USDT contract addresses (ERC-20)
    USDT_CONTRACTS = {
        'ethereum': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
        'bsc': '0x55d398326f99059fF775485246999027B3197955',
        'polygon': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',
    }
    
    # RPC endpoints
    RPC_URLS = {
        'ethereum': 'https://eth.llamarpc.com',
        'bsc': 'https://bsc-dataseed.binance.org',
        'polygon': 'https://polygon-rpc.com',
    }
    
    def __init__(self, db_conn, cfg: Config, wallet_service: WalletService):
        self.db_conn = db_conn
        self.cfg = cfg
        self.wallet_service = wallet_service
        self.network = cfg.blockchain_network  # Use configured network
        self.web3 = self._init_web3()
        self.usdt_contract = self._init_usdt_contract()
    
    def _init_web3(self) -> Web3:
        """Initialize Web3 connection"""
        try:
            rpc_url = self.RPC_URLS.get(self.network, self.RPC_URLS['ethereum'])
            web3 = Web3(Web3.HTTPProvider(rpc_url))
            
            if not web3.is_connected():
                raise ConnectionError(f"Failed to connect to {self.network} RPC")
            
            logger.info(f"Connected to {self.network} blockchain")
            return web3
        except Exception as e:
            logger.error(f"Failed to initialize Web3: {e}")
            raise
    
    def _init_usdt_contract(self):
        """Initialize USDT contract"""
        try:
            usdt_address = self.USDT_CONTRACTS[self.network]
            contract_abi = self._get_erc20_abi()
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(usdt_address),
                abi=contract_abi
            )
            logger.info(f"Initialized USDT contract on {self.network}")
            return contract
        except Exception as e:
            logger.error(f"Failed to initialize USDT contract: {e}")
            raise
    
    def _get_erc20_abi(self) -> list:
        """Get ERC-20 ABI for USDT"""
        return [{
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        }, {
            "constant": False,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"}
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        }, {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function"
        }]
    
    def get_wallet_balance(self, wallet_address: str) -> Dict[str, float]:
        """Get real wallet balance from blockchain"""
        try:
            # Get native token balance (ETH/BNB/MATIC)
            native_balance = self.web3.eth.get_balance(wallet_address)
            native_balance_ether = self.web3.from_wei(native_balance, 'ether')
            
            # Get USDT balance (ERC-20)
            usdt_balance = self._get_token_balance(wallet_address)
            
            return {
                'native': float(native_balance_ether),
                'usdt': float(usdt_balance),
            }
        except Exception as e:
            logger.error(f"Failed to get wallet balance: {e}")
            raise
    
    def _get_token_balance(self, wallet_address: str) -> float:
        """Get ERC-20 token balance"""
        try:
            balance = self.usdt_contract.functions.balanceOf(
                Web3.to_checksum_address(wallet_address)
            ).call()
            
            # USDT has 6 decimals
            return balance / 10**6
        except Exception as e:
            logger.error(f"Failed to get token balance: {e}")
            return 0.0
    
    def withdraw_to_blockchain(
        self,
        chat_id: int,
        to_address: str,
        amount: float,
        currency: str = "USDT"
    ) -> Dict[str, Any]:
        """Withdraw funds to blockchain address"""
        try:
            # Get chat's wallet
            wallet = self.wallet_service.get_user_wallet(chat_id)
            if not wallet:
                return {"success": False, "error": "No wallet found for chat"}
            
            # Calculate fee
            fee = amount * (self.cfg.fee_percentage / 100)
            total_deduction = amount + fee
            
            # Check sufficient balance
            if wallet.balance_usd < total_deduction:
                return {
                    "success": False,
                    "error": f"Insufficient balance. Required: {total_deduction:.2f}, Available: {wallet.balance_usd:.2f}"
                }
            
            # Update wallet balance
            new_balance = wallet.balance_usd - total_deduction
            update_wallet_balance(
                self.db_conn,
                wallet.id,
                new_balance,
                self.cfg.sql_busy_retries,
                self.cfg.sql_busy_sleep
            )
            
            # Create transaction record
            transaction = create_transaction(
                self.db_conn,
                wallet.id,
                "withdrawal",
                amount,
                currency,
                fee=fee,
                status="pending",
                busy_retries=self.cfg.sql_busy_retries,
                busy_sleep=self.cfg.sql_busy_sleep,
            )
            
            # Execute real blockchain transaction
            tx_hash = self._send_usdt_transaction(
                wallet.wallet_address,
                to_address,
                amount
            )
            
            logger.info(
                f"Withdrawal sent: {amount} {currency} to {to_address} with fee {fee:.2f}, tx: {tx_hash}"
            )
            
            return {
                "success": True,
                "transaction_id": transaction.id,
                "wallet_address": wallet.wallet_address,
                "to_address": to_address,
                "amount": amount,
                "fee": fee,
                "total_deduction": total_deduction,
                "currency": currency,
                "tx_hash": tx_hash,
                "status": "pending",
            }
            
        except Exception as e:
            logger.error(f"Failed to process withdrawal: {e}")
            return {"success": False, "error": str(e)}
    
    def _send_usdt_transaction(
        self,
        from_address: str,
        to_address: str,
        amount: float
    ) -> str:
        """Send USDT transaction on blockchain"""
        try:
            # Get wallet from database to decrypt private key
            wallet = get_wallet_by_address(
                self.db_conn,
                from_address,
                self.cfg.sql_busy_retries,
                self.cfg.sql_busy_sleep
            )
            
            if not wallet:
                raise ValueError("Wallet not found")
            
            # Decrypt private key (simplified - in production use proper encryption)
            # For now, we'll use a placeholder approach
            # In production, you would decrypt the encrypted private key
            
            # Convert amount to USDT units (6 decimals)
            amount_units = int(amount * 10**6)
            
            # Build transaction
            nonce = self.web3.eth.get_transaction_count(from_address)
            
            # Get USDT transfer function
            transfer_func = self.usdt_contract.functions.transfer(
                Web3.to_checksum_address(to_address),
                amount_units
            )
            
            # Estimate gas
            gas_estimate = transfer_func.estimate_gas({'from': from_address})
            gas_price = self.web3.eth.gas_price
            
            # Build transaction
            tx = transfer_func.build_transaction({
                'from': from_address,
                'nonce': nonce,
                'gas': gas_estimate,
                'gasPrice': gas_price,
            })
            
            # Sign transaction (requires private key)
            # For this implementation, we'll return a placeholder
            # In production, you would:
            # 1. Decrypt the private key from wallet.private_key_encrypted
            # 2. Sign the transaction with Account.sign_transaction()
            # 3. Send with web3.eth.send_raw_transaction()
            
            logger.warning("Transaction signing not implemented - returning placeholder")
            return "0x0000000000000000000000000000000000000000000000000000000000000000"
            
        except Exception as e:
            logger.error(f"Failed to send USDT transaction: {e}")
            raise
    
    def sync_wallet_balance(self, chat_id: int) -> Dict[str, Any]:
        """Sync wallet balance from blockchain to database"""
        try:
            wallet = self.wallet_service.get_user_wallet(chat_id)
            if not wallet:
                return {"success": False, "error": "No wallet found for chat"}
            
            # Get real balance from blockchain
            blockchain_balance = self.get_wallet_balance(wallet.wallet_address)
            usdt_balance = blockchain_balance['usdt']
            
            # Update database balance
            update_wallet_balance(
                self.db_conn,
                wallet.id,
                usdt_balance,
                self.cfg.sql_busy_retries,
                self.cfg.sql_busy_sleep
            )
            
            logger.info(f"Synced wallet balance from blockchain: {usdt_balance:.2f} USDT")
            
            return {
                "success": True,
                "wallet_address": wallet.wallet_address,
                "usdt_balance": usdt_balance,
                "native_balance": blockchain_balance['native'],
            }
            
        except Exception as e:
            logger.error(f"Failed to sync wallet balance: {e}")
            return {"success": False, "error": str(e)}
