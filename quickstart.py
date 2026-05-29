#!/usr/bin/env python
"""
Quick Start Script for Trading Bot
Runs all tests and validates production readiness
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"▶ {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=False)
        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
            return True
        else:
            print(f"❌ {description} - FAILED")
            return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False


def main():
    """Run quickstart sequence"""
    print("""
╔════════════════════════════════════════════════════════════╗
║     TRADING BOT - QUICK START & PRODUCTION VALIDATOR       ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    results = {}
    
    # Step 1: Install dependencies
    results['install'] = run_command(
        f"{sys.executable} -m pip install -q -r requirements.txt",
        "Step 1/5: Installing dependencies"
    )
    
    if not results['install']:
        print("\n❌ Failed to install dependencies. Aborting.")
        return 1
    
    # Step 2: Run unit tests
    results['unit_tests'] = run_command(
        f"{sys.executable} -m pytest cmd/test/test_unit.py -v --tb=short",
        "Step 2/5: Running unit tests"
    )
    
    # Step 3: Run integration tests
    results['integration'] = run_command(
        f"{sys.executable} cmd/test/test_trading_api.py",
        "Step 3/5: Running integration tests"
    )
    
    # Step 4: Production setup
    results['setup'] = run_command(
        f"{sys.executable} scripts/production_setup.py",
        "Step 4/5: Creating production configuration"
    )
    
    # Step 5: Production validation
    results['validation'] = run_command(
        f"{sys.executable} internal/services/production_validator.py",
        "Step 5/5: Validating production readiness"
    )
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for step, passed_flag in results.items():
        status = "✅ PASS" if passed_flag else "❌ FAIL"
        print(f"{status} - {step}")
    
    print(f"\nResult: {passed}/{total} steps passed")
    
    if passed == total:
        print(f"\n{'='*60}")
        print("🎉 ALL TESTS PASSED - SYSTEM IS READY FOR DEPLOYMENT")
        print(f"{'='*60}")
        print("""
Next steps:
1. Update .env with your API keys:
   cp .env.template .env
   nano .env

2. Start the API server:
   python cmd/server/api_server.py

3. Test the API:
   curl http://localhost:5000/health

4. Deploy using one of:
   - Docker: docker-compose up -d
   - Systemd: sudo systemctl start trading-bot-api
   - Manual: gunicorn -w 4 cmd.server.api_server:app
        """)
        return 0
    else:
        print(f"\n{'='*60}")
        print("⚠ SOME TESTS FAILED - FIX ISSUES BEFORE DEPLOYMENT")
        print(f"{'='*60}")
        print("""
Failed steps:
""")
        for step, passed_flag in results.items():
            if not passed_flag:
                print(f"  - {step}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
