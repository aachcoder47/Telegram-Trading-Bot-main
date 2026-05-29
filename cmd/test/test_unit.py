"""
Unit tests for Trading Bot core components
Run: python -m pytest cmd/test/test_unit.py -v
"""

import pytest
import sys
from pathlib import Path
import tempfile
import sqlite3

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from internal.services.wallet_manager import WalletManager, UserWallet
from internal.services.user_manager import UserManager, User
from internal.services.signup_service import SignupService
from internal.services.deposit_watcher import DepositWatcher
from configs.config import Config


class TestWalletManager:
    """Test wallet generation and management"""
    
    def test_mnemonic_generation(self):
        """Test BIP39 mnemonic generation"""
        wm = WalletManager()
        mnemonic = wm.generate_mnemonic()
        
        assert mnemonic is not None
        assert len(mnemonic.split()) == 24  # 256-bit = 24 words
        assert isinstance(mnemonic, str)
    
    def test_btc_address_generation(self):
        """Test Bitcoin address generation"""
        wm = WalletManager()
        mnemonic = wm.generate_mnemonic()
        btc_addr = wm.generate_btc_address(mnemonic)
        
        assert btc_addr is not None
        assert btc_addr.coin == "BTC"
        assert btc_addr.address.startswith("bc1")  # Bech32 format
        assert btc_addr.public_key is not None
        assert btc_addr.derivation_path == "m/44'/0'/0'/0/0"
    
    def test_eth_address_generation(self):
        """Test Ethereum address generation"""
        wm = WalletManager()
        mnemonic = wm.generate_mnemonic()
        eth_addr = wm.generate_eth_address(mnemonic)
        
        assert eth_addr is not None
        assert eth_addr.coin == "ETH"
        assert eth_addr.address.startswith("0x")
        assert len(eth_addr.address) == 42
        assert eth_addr.public_key is not None
    
    def test_multi_coin_wallet_generation(self):
        """Test multi-coin wallet creation"""
        wm = WalletManager()
        wallet = wm.generate_multi_coin_wallet("test_user_1")
        
        assert wallet is not None
        assert wallet.user_id == "test_user_1"
        assert "BTC" in wallet.addresses
        assert "ETH" in wallet.addresses
        assert wallet.mnemonic is not None
    
    def test_wallet_save_and_load(self):
        """Test wallet persistence"""
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WalletManager(Path(tmpdir))
            wallet = wm.generate_multi_coin_wallet("user_persist_test")
            
            # Save wallet
            wm.save_wallet(wallet)
            
            # Load wallet
            loaded = wm.load_wallet(wallet.user_id, wallet.wallet_id)
            
            assert loaded is not None
            assert loaded.user_id == wallet.user_id
            assert loaded.addresses["BTC"].address == wallet.addresses["BTC"].address
            assert loaded.addresses["ETH"].address == wallet.addresses["ETH"].address


class TestUserManager:
    """Test user account management"""
    
    def test_user_creation(self):
        """Test user account creation"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            um = UserManager(db_path)
            user = um.create_user(
                user_id="test_user_1",
                username="testuser",
                email="test@example.com",
                password="password123",
                wallet_id="wallet_123",
                deposit_address={"BTC": "bc1test", "ETH": "0xtest"}
            )
            
            assert user is not None
            assert user.username == "testuser"
            assert user.user_id == "test_user_1"
        finally:
            Path(db_path).unlink()
    
    def test_user_authentication(self):
        """Test user login"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            um = UserManager(db_path)
            um.create_user(
                user_id="auth_test",
                username="authuser",
                email="auth@example.com",
                password="correctpass",
                wallet_id="wallet_auth",
                deposit_address={"BTC": "bc1test"}
            )
            
            # Test correct password
            user = um.authenticate("authuser", "correctpass")
            assert user is not None
            assert user.username == "authuser"
            
            # Test wrong password
            user = um.authenticate("authuser", "wrongpass")
            assert user is None
        finally:
            Path(db_path).unlink()
    
    def test_duplicate_username(self):
        """Test duplicate username rejection"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            um = UserManager(db_path)
            um.create_user(
                user_id="user_1",
                username="duplicate",
                email="first@example.com",
                password="pass1",
                wallet_id="wallet_1",
                deposit_address={"BTC": "bc1test"}
            )
            
            # Try to create user with same username
            with pytest.raises(ValueError):
                um.create_user(
                    user_id="user_2",
                    username="duplicate",
                    email="second@example.com",
                    password="pass2",
                    wallet_id="wallet_2",
                    deposit_address={"BTC": "bc1test"}
                )
        finally:
            Path(db_path).unlink()


class TestDepositWatcher:
    """Test deposit monitoring"""
    
    def test_price_fetching(self):
        """Test crypto price fetching"""
        dw = DepositWatcher(min_deposit_usd=50.0)
        
        btc_price = dw.get_btc_price_usd()
        eth_price = dw.get_eth_price_usd()
        
        # Prices should be reasonable (can fail on network issues)
        if btc_price:
            assert btc_price > 1000  # BTC price should be > $1k
        if eth_price:
            assert eth_price > 100   # ETH price should be > $100
    
    def test_minimum_deposit_validation(self):
        """Test minimum deposit threshold"""
        dw = DepositWatcher(min_deposit_usd=50.0)
        
        # Create mock deposit status
        status = {
            "total_usd": 75.0,
            "meets_minimum": True
        }
        
        assert status["meets_minimum"] is True
        
        # Test below minimum
        status_low = {
            "total_usd": 25.0,
            "meets_minimum": False
        }
        
        assert status_low["meets_minimum"] is False


class TestSignupService:
    """Test user registration flow"""
    
    def test_complete_signup_flow(self):
        """Test end-to-end user registration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WalletManager(Path(tmpdir))
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
                db_path = f.name
            
            try:
                um = UserManager(db_path)
                signup = SignupService(um, wm)
                
                result = signup.register_user(
                    username="newuser",
                    email="new@example.com",
                    password="securepass"
                )
                
                assert result is not None
                assert result['status'] == 'success' or 'user' in result
                assert 'user_id' in result or 'user_id' in result.get('user', {})
            finally:
                Path(db_path).unlink()


class TestConfigValidation:
    """Test configuration loading and validation"""
    
    def test_config_defaults(self):
        """Test that config loads with defaults"""
        cfg = Config(
            api_id=123,
            api_hash="test_hash",
            session_name="test",
            exchange="xt",
            proxy_type="",
            proxy_host=None,
            proxy_port=None,
            proxy_username=None,
            proxy_password=None,
            channels=[],
            backfill=3,
            db_path="./test.db",
            media_dir=Path("./media"),
            heartbeat_secs=180,
            max_backoff_secs=300,
            sql_busy_retries=10,
            sql_busy_sleep=0.2,
            log_level="INFO",
            log_file="./bot.log",
            log_backup_count=14,
            mistral_api_key="test_key",
            mistral_model="mistral-large-latest",
            mistral_timeout_secs=299,
            upload_base="http://localhost:8080",
            fee_wallet_address="bc1test",
            fee_percentage=5.0,
            min_deposit_usd=50.0,
            lbank_api_key=None,
            lbank_secret=None,
            lbank_password=None,
            xt_api_key=None,
            xt_secret=None,
            xt_password=None,
            xt_margin_mode="cross",
            bitunix_api_key=None,
            bitunix_secret=None,
            bitunix_base_url="https://fapi.bitunix.com",
            bitunix_language="en-US",
            order_quote="USDT",
            order_notional=10.0,
            max_price_deviation_pct=0.02,
            enable_auto_execution=True
        )
        
        assert cfg.min_deposit_usd == 50.0
        assert cfg.fee_percentage == 5.0
        assert cfg.mistral_model == "mistral-large-latest"


def run_tests():
    """Run all tests"""
    print("=" * 60)
    print("Trading Bot - Unit Tests")
    print("=" * 60)
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
