"""
Deposit monitoring and confirmation service
Watches for incoming deposits and confirms transactions
"""

import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional, List

import requests


logger = logging.getLogger(__name__)


class DepositWatcher:
    """Monitors blockchain for incoming deposits"""
    
    def __init__(self, min_deposit_usd: float = 50.0):
        self.min_deposit_usd = min_deposit_usd
        self.bitcoin_rpc = "https://blockstream.info/api"
        self.ethereum_rpc = "https://api.etherscan.io/api"
    
    def get_btc_price_usd(self) -> Optional[float]:
        """Get current BTC price in USD"""
        try:
            response = requests.get("https://api.coinbase.com/v2/exchange-rates?currency=BTC", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return float(data["data"]["rates"]["USD"])
        except Exception as e:
            logger.warning(f"Failed to fetch BTC price: {e}")
        return None
    
    def get_eth_price_usd(self) -> Optional[float]:
        """Get current ETH price in USD"""
        try:
            response = requests.get("https://api.coinbase.com/v2/exchange-rates?currency=ETH", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return float(data["data"]["rates"]["USD"])
        except Exception as e:
            logger.warning(f"Failed to fetch ETH price: {e}")
        return None
    
    def check_btc_address(self, address: str) -> Dict:
        """Check Bitcoin address for unconfirmed and confirmed transactions"""
        try:
            # Get address data
            response = requests.get(
                f"{self.bitcoin_rpc}/address/{address}",
                timeout=10
            )
            if response.status_code != 200:
                logger.warning(f"Failed to check BTC address {address}")
                return {"balance": 0, "transactions": []}
            
            data = response.json()
            
            # Get transactions
            tx_list = []
            for tx in data.get("chain_stats", {}).get("tx_count", 0):
                tx_list.append({
                    "txid": tx.get("txid"),
                    "amount_satoshi": tx.get("value", 0),
                    "confirmed": tx.get("status", {}).get("confirmed", False)
                })
            
            btc_price = self.get_btc_price_usd()
            total_btc = data.get("chain_stats", {}).get("funded_txo_sum", 0) / 1e8
            total_usd = total_btc * (btc_price or 0)
            
            return {
                "coin": "BTC",
                "address": address,
                "balance_btc": total_btc,
                "balance_usd": total_usd,
                "transactions": tx_list,
                "meets_minimum": total_usd >= self.min_deposit_usd
            }
            
        except Exception as e:
            logger.error(f"Failed to check BTC address {address}: {e}")
            return {"balance": 0, "transactions": [], "meets_minimum": False}
    
    def check_eth_address(self, address: str, etherscan_api_key: str = None) -> Dict:
        """Check Ethereum address for incoming transactions"""
        try:
            if not etherscan_api_key:
                logger.warning("Etherscan API key not provided, skipping ETH check")
                return {"balance": 0, "transactions": [], "meets_minimum": False}
            
            # Get ETH balance
            response = requests.get(
                f"{self.ethereum_rpc}?module=account&action=balance&address={address}&apikey={etherscan_api_key}",
                timeout=10
            )
            if response.status_code != 200:
                logger.warning(f"Failed to check ETH address {address}")
                return {"balance": 0, "transactions": [], "meets_minimum": False}
            
            balance_data = response.json()
            balance_wei = int(balance_data.get("result", 0))
            balance_eth = balance_wei / 1e18
            
            # Get ETH price
            eth_price = self.get_eth_price_usd()
            balance_usd = balance_eth * (eth_price or 0)
            
            # Get transactions
            tx_response = requests.get(
                f"{self.ethereum_rpc}?module=account&action=txlist&address={address}&sort=desc&apikey={etherscan_api_key}",
                timeout=10
            )
            
            tx_list = []
            if tx_response.status_code == 200:
                tx_data = tx_response.json()
                for tx in tx_data.get("result", [])[:10]:  # Last 10 transactions
                    tx_list.append({
                        "hash": tx.get("hash"),
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "amount_eth": float(tx.get("value", 0)) / 1e18,
                        "confirmed": int(tx.get("confirmations", 0)) > 0
                    })
            
            return {
                "coin": "ETH",
                "address": address,
                "balance_eth": balance_eth,
                "balance_usd": balance_usd,
                "transactions": tx_list,
                "meets_minimum": balance_usd >= self.min_deposit_usd
            }
            
        except Exception as e:
            logger.error(f"Failed to check ETH address {address}: {e}")
            return {"balance": 0, "transactions": [], "meets_minimum": False}
    
    def check_deposit_status(
        self,
        deposit_addresses: Dict[str, str],
        etherscan_api_key: str = None
    ) -> Dict:
        """Check all deposit addresses for received funds"""
        status = {
            "total_usd": 0,
            "coins": {},
            "meets_minimum": False,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check Bitcoin
        if "BTC" in deposit_addresses:
            btc_check = self.check_btc_address(deposit_addresses["BTC"])
            status["coins"]["BTC"] = btc_check
            status["total_usd"] += btc_check.get("balance_usd", 0)
        
        # Check Ethereum
        if "ETH" in deposit_addresses:
            eth_check = self.check_eth_address(
                deposit_addresses["ETH"],
                etherscan_api_key
            )
            status["coins"]["ETH"] = eth_check
            status["total_usd"] += eth_check.get("balance_usd", 0)
        
        status["meets_minimum"] = status["total_usd"] >= self.min_deposit_usd
        
        return status
    
    async def watch_deposits(
        self,
        user_id: str,
        deposit_addresses: Dict[str, str],
        user_manager,
        etherscan_api_key: str = None,
        poll_interval_secs: int = 60,
        max_wait_secs: int = 3600
    ) -> bool:
        """
        Watch for deposits until minimum is reached or timeout
        Returns True if deposit confirmed and meets minimum
        """
        start_time = datetime.utcnow()
        check_count = 0
        
        while True:
            check_count += 1
            
            # Check deposit status
            status = self.check_deposit_status(deposit_addresses, etherscan_api_key)
            
            logger.info(
                f"Deposit check #{check_count} for user {user_id}: "
                f"${status['total_usd']:.2f} (needs ${self.min_deposit_usd})"
            )
            
            # If minimum met, record deposit and return
            if status["meets_minimum"]:
                deposit_id = f"dep_{uuid.uuid4().hex[:12]}"
                
                for coin, coin_status in status["coins"].items():
                    if coin_status.get("balance_usd", 0) > 0:
                        user_manager.record_deposit(
                            deposit_id=deposit_id,
                            user_id=user_id,
                            coin=coin,
                            amount=coin_status.get(f"balance_{coin.lower()}", 0),
                            tx_hash=None
                        )
                        user_manager.confirm_deposit(deposit_id)
                
                logger.info(f"Deposit confirmed for user {user_id}: ${status['total_usd']:.2f}")
                return True
            
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > max_wait_secs:
                logger.warning(
                    f"Deposit timeout for user {user_id} after {check_count} checks"
                )
                return False
            
            # Wait before next check
            await asyncio.sleep(poll_interval_secs)
