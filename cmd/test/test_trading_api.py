"""
Quick test script for Trading Bot API
Demonstrates user registration, login, and deposit checking
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from configs.config import load_config
from internal.services.trading_bot_api import TradingBotAPI


def test_api():
    """Test trading bot API"""
    print("=" * 60)
    print("Trading Bot API - Quick Test")
    print("=" * 60)
    
    cfg = load_config()
    api = TradingBotAPI(cfg)
    
    # Test 1: Register a new user
    print("\n[TEST 1] User Registration")
    print("-" * 40)
    registration = api.register(
        username="testuser123",
        email="testuser@example.com",
        password="securepass123"
    )
    print(f"Status: {registration['status']}")
    if registration['status'] == 'success':
        user_info = registration['user']
        print(f"User ID: {user_info['user_id']}")
        print(f"Wallet ID: {user_info['wallet_id']}")
        print(f"Deposit Addresses:")
        for coin, addr in user_info['deposit_addresses'].items():
            print(f"  {coin}: {addr}")
        
        user_id = user_info['user_id']
    else:
        print(f"Error: {registration.get('message')}")
        return
    
    # Test 2: Login
    print("\n[TEST 2] User Login")
    print("-" * 40)
    login = api.login(username="testuser123", password="securepass123")
    print(f"Status: {login['status']}")
    if login['status'] == 'success':
        print(f"Logged in: {login['username']}")
    else:
        print(f"Error: {login.get('message')}")
    
    # Test 3: Get user info
    print("\n[TEST 3] Get User Info")
    print("-" * 40)
    user_info = api.get_user_info(user_id)
    print(f"Status: {user_info['status']}")
    if user_info['status'] == 'success':
        user = user_info['user']
        print(f"Username: {user['username']}")
        print(f"Email: {user['email']}")
        print(f"Total Balance: ${user['total_balance_usd']:.2f}")
        print(f"Total Profit: ${user['total_profit_usd']:.2f}")
        print(f"Fees Paid: ${user['fees_paid_usd']:.2f}")
    
    # Test 4: Get deposit addresses
    print("\n[TEST 4] Get Deposit Addresses")
    print("-" * 40)
    deposits = api.get_deposit_addresses(user_id)
    print(f"Status: {deposits['status']}")
    if deposits['status'] == 'success':
        print(f"Minimum Required: ${deposits['min_required_usd']:.2f}")
        print(f"Deposit Addresses:")
        for coin, addr in deposits['deposit_addresses'].items():
            print(f"  {coin}: {addr}")
    
    # Test 5: Check deposit status
    print("\n[TEST 5] Check Deposit Status")
    print("-" * 40)
    status = api.check_deposit_status(user_id)
    print(f"Status: {status['status']}")
    if status['status'] == 'success':
        deposit = status['deposit_status']
        print(f"Total Balance: ${deposit['total_usd']:.2f}")
        print(f"Meets Minimum: {deposit['meets_minimum']}")
        for coin, coin_status in deposit['coins'].items():
            print(f"\n  {coin}:")
            print(f"    Balance: ${coin_status.get('balance_usd', 0):.2f}")
            print(f"    Meets minimum: {coin_status.get('meets_minimum', False)}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_api()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
