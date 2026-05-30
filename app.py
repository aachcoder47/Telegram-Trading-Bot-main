import asyncio
import logging
import sys

from configs.config import load_config
from internal.db.sqlite import connect_db, init_db
from api.telegram.client import build_client
from api.telegram.wallet_handlers import register_wallet_handlers
from internal.services.wallet_service import WalletService
from internal.services.internal_trading import InternalTradingService
from internal.services.real_blockchain_deposits import RealBlockchainWalletService
from pkg.logger import setup_logging


async def run_wallet_bot(cfg):
    """Run the wallet-based trading bot"""
    db_conn = init_db(cfg.db_path)

    client = build_client(cfg)

    # Initialize services
    wallet_service = WalletService(db_conn, cfg)
    
    # Use simulated trading for now (can be replaced with real trading later)
    trading_service = InternalTradingService(db_conn, cfg, wallet_service)
    logging.getLogger(__name__).info("Using SIMULATED trading (internal)")
    
    # Initialize blockchain wallet service for real deposits/withdrawals
    blockchain_service = RealBlockchainWalletService(db_conn, cfg, wallet_service)
    logging.getLogger(__name__).info("Using REAL blockchain wallet (Ethereum/BSC/Polygon)")

    # Register wallet handlers
    register_wallet_handlers(client, cfg, db_conn, wallet_service, trading_service, blockchain_service)

    attempts = 0
    while True:
        try:
            logging.getLogger(__name__).info("Connecting to Telegram...")
            await client.connect()

            if not await client.is_user_authorized():
                logging.getLogger(__name__).info("Authorizing... (enter your phone/code/2FA)")
                await client.start()

            logging.getLogger(__name__).info("Wallet Trading Bot is running!")
            logging.getLogger(__name__).info("Use /help to see available commands")

            await client.run_until_disconnected()

            logging.getLogger(__name__).critical("Telegram client disconnected")
            raise ConnectionError("Disconnected")

        except Exception as e:
            attempts += 1
            backoff = min(cfg.max_backoff_secs, (2 ** min(attempts, 6)))
            logging.getLogger(__name__).error(f"Connection error: {e}. Reconnecting in {int(backoff)}s...")
            await asyncio.sleep(backoff)
            continue
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        cfg = load_config()
        setup_logging(cfg)

        # Check for required Mistral API key
        if not cfg.mistral_api_key:
            logging.getLogger(__name__).error("MISTRAL_API_KEY is required for AI signal extraction")
            sys.exit(1)

        asyncio.run(run_wallet_bot(cfg))
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Stopped by user.")
