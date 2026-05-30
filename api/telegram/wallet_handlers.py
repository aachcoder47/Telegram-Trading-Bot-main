from telethon import events
import logging

from internal.services.wallet_service import WalletService
from internal.services.internal_trading import InternalTradingService
from internal.services.real_blockchain_deposits import RealBlockchainWalletService
from configs.config import Config

logger = logging.getLogger(__name__)


def register_wallet_handlers(client, cfg: Config, db_conn, wallet_service: WalletService, trading_service, blockchain_service):
    """Register wallet-related command handlers"""

    @client.on(events.NewMessage(pattern=r'/start'))
    async def on_start(event):
        """Welcome message for new users"""
        welcome_message = """
🤖 Welcome to the AI Trading Bot!

I'm your personal cryptocurrency trading assistant with built-in wallet management.

🚀 Quick Start Guide:

1️⃣ Create your wallet: /create_wallet
2️⃣ Check your balance: /balance
3️⃣ Start trading: /trade BTC long

💡 Use /help to see all available commands

🔒 Your funds are secure with our custodial wallet system
📊 AI-powered trading signals from Mistral
💰 7.5% fee only on withdrawals

Let's get started! Type /create_wallet to begin.
        """
        await event.reply(welcome_message)

    @client.on(events.NewMessage(pattern=r'/create_wallet'))
    async def on_create_wallet(event):
        """Create a new wallet for the user"""
        try:
            chat_id = event.chat_id
            wallet = wallet_service.create_user_wallet(chat_id)
            
            await event.reply(
                f"🎉 Congratulations! Your wallet has been created!\n\n"
                f"📍 Your Wallet Address:\n`{wallet.wallet_address}`\n\n"
                f"💰 Current Balance: ${wallet.balance_usd:.2f} USD\n\n"
                f"📝 Next Steps:\n"
                f"• Deposit funds using /deposit\n"
                f"• Check balance with /balance\n"
                f"• Start trading with /trade\n\n"
                f"💡 Tip: Copy your wallet address and send USDT to it to start trading!",
                parse_mode='markdown'
            )
        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            await event.reply(
                f"❌ Oops! Something went wrong while creating your wallet.\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again or contact support if the issue persists."
            )

    @client.on(events.NewMessage(pattern=r'/wallet'))
    async def on_wallet_info(event):
        """Show wallet information"""
        try:
            chat_id = event.chat_id
            wallet = wallet_service.get_user_wallet(chat_id)
            
            if not wallet:
                await event.reply(
                    "💼 You don't have a wallet yet!\n\n"
                    "👉 Create one with /create_wallet to get started."
                )
                return
            
            balance = wallet_service.get_wallet_balance(chat_id)
            positions = trading_service.get_user_positions(chat_id)
            
            position_info = "\n".join([
                f"• {pos.token} {pos.position_type.upper()}: {pos.quantity:.6f} @ ${pos.entry_price:.2f}"
                for pos in positions
            ]) if positions else "✨ No open positions"
            
            await event.reply(
                f"💼 Your Wallet\n\n"
                f"📍 Address: `{wallet.wallet_address}`\n"
                f"💰 Balance: ${balance:.2f} USD\n\n"
                f"📊 Open Positions:\n{position_info}\n\n"
                f"💡 Use /deposit to add funds or /trade to start trading!",
                parse_mode='markdown'
            )
        except Exception as e:
            logger.error(f"Error showing wallet info: {e}")
            await event.reply(
                f"❌ Sorry, I couldn't retrieve your wallet information.\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again later."
            )

    @client.on(events.NewMessage(pattern=r'/deposit'))
    async def on_deposit(event):
        """Show deposit instructions and sync balance"""
        try:
            chat_id = event.chat_id
            wallet = wallet_service.get_user_wallet(chat_id)
            
            if not wallet:
                await event.reply("❌ No wallet found. Use /create_wallet to create one.")
                return
            
            # Sync balance from blockchain if available
            if blockchain_service:
                sync_result = blockchain_service.sync_wallet_balance(chat_id)
                
                if sync_result['success']:
                    await event.reply(
                        f"💳 Deposit Instructions\n\n"
                        f"Send USDT (ERC-20) to:\n"
                        f"`{wallet.wallet_address}`\n\n"
                        f"🌐 Network: Ethereum (ERC-20)\n"
                        f"💰 Current Balance: ${sync_result['usdt_balance']:.2f} USDT\n"
                        f"⛽ Native Balance: {sync_result['native_balance']:.6f} ETH\n\n"
                        f"✅ Balance synced from blockchain!\n\n"
                        f"Use /balance to check your balance anytime.",
                        parse_mode='markdown'
                    )
                else:
                    await event.reply(
                        f"💳 Deposit Instructions\n\n"
                        f"Send USDT (ERC-20) to:\n"
                        f"`{wallet.wallet_address}`\n\n"
                        f"🌐 Network: Ethereum (ERC-20)\n"
                        f"⚠️ Balance sync failed. Use /sync to try again.",
                        parse_mode='markdown'
                    )
            else:
                await event.reply(
                    f"💳 Deposit Instructions\n\n"
                    f"Send USDT (ERC-20) to:\n"
                    f"`{wallet.wallet_address}`\n\n"
                    f"🌐 Network: Ethereum (ERC-20)\n"
                    f"⚠️ Blockchain features unavailable - using simulated wallet",
                    parse_mode='markdown'
                )
        except Exception as e:
            logger.error(f"Error showing deposit info: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(pattern=r'/balance'))
    async def on_balance(event):
        """Show wallet balance from blockchain"""
        try:
            chat_id = event.chat_id
            wallet = wallet_service.get_user_wallet(chat_id)
            
            if not wallet:
                await event.reply("❌ No wallet found. Use /create_wallet to create one.")
                return
            
            # Sync balance from blockchain
            sync_result = blockchain_service.sync_wallet_balance(chat_id)
            
            if sync_result['success']:
                await event.reply(
                    f"💰 Wallet Balance\n\n"
                    f"📍 Address: `{wallet.wallet_address}`\n"
                    f"💵 USDT: ${sync_result['usdt_balance']:.2f}\n"
                    f"⛽ Native (ETH): {sync_result['native_balance']:.6f}\n\n"
                    f"✅ Balance synced from blockchain!",
                    parse_mode='markdown'
                )
            else:
                await event.reply(
                    f"❌ Failed to sync balance from blockchain.\n\n"
                    f"Error: {sync_result.get('error', 'Unknown error')}\n\n"
                    f"Use /sync to try again."
                )
        except Exception as e:
            logger.error(f"Error showing balance: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(pattern=r'/sync'))
    async def on_sync(event):
        """Sync wallet balance from blockchain"""
        try:
            chat_id = event.chat_id
            sync_result = blockchain_service.sync_wallet_balance(chat_id)
            
            if sync_result['success']:
                await event.reply(
                    f"✅ Balance synced successfully!\n\n"
                    f"💰 USDT: ${sync_result['usdt_balance']:.2f}\n"
                    f"⛽ Native (ETH): {sync_result['native_balance']:.6f}",
                    parse_mode='markdown'
                )
            else:
                await event.reply(
                    f"❌ Sync failed.\n\n"
                    f"Error: {sync_result.get('error', 'Unknown error')}"
                )
        except Exception as e:
            logger.error(f"Error syncing balance: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(pattern=r'/withdraw'))
    async def on_withdraw(event):
        """Withdraw funds to blockchain address"""
        try:
            chat_id = event.chat_id
            # Parse amount and address from message
            message_text = event.message.message
            parts = message_text.split()
            
            if len(parts) < 3:
                await event.reply("Usage: /withdraw <amount> <address> [currency]\nExample: /withdraw 100 0x1234...abcd USDT")
                return
            
            try:
                amount = float(parts[1])
                to_address = parts[2]
                currency = parts[3] if len(parts) > 3 else "USDT"
            except ValueError:
                await event.reply("❌ Invalid amount. Please provide a valid number.")
                return
            
            # Validate address format
            if not to_address.startswith('0x') or len(to_address) != 42:
                await event.reply("❌ Invalid address format. Must be a valid Ethereum address (0x...)")
                return
            
            # Execute blockchain withdrawal
            result = blockchain_service.withdraw_to_blockchain(chat_id, to_address, amount, currency)
            
            if result['success']:
                await event.reply(
                    f"✅ Withdrawal initiated!\n\n"
                    f"💵 Amount: ${amount:.2f} {currency}\n"
                    f"💸 Fee (7.5%): ${result['fee']:.2f} {currency}\n"
                    f"📉 Total deducted: ${result['total_deduction']:.2f} {currency}\n"
                    f"📍 To: `{to_address}`\n"
                    f"🔗 TX: `{result['tx_hash']}`\n\n"
                    f"⏳ Transaction pending blockchain confirmation...",
                    parse_mode='markdown'
                )
            else:
                await event.reply(f"❌ Withdrawal failed: {result['error']}")
        except Exception as e:
            logger.error(f"Error processing withdrawal: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(pattern=r'/trade'))
    async def on_trade(event):
        """Execute a trade based on AI analysis"""
        try:
            chat_id = event.chat_id
            message_text = event.message.message
            parts = message_text.split()
            
            if len(parts) < 3:
                await event.reply(
                    "Usage: /trade <token> <long|short> [amount]\n"
                    "Example: /trade BTC long 100\n\n"
                    "The AI will analyze the market and execute the trade."
                )
                return
            
            token = parts[1].upper()
            position_type = parts[2].lower()
            amount = float(parts[3]) if len(parts) > 3 else None
            
            if position_type not in ['long', 'short']:
                await event.reply("❌ Invalid position type. Use 'long' or 'short'.")
                return
            
            # Execute trade directly (AI analysis optional)
            result = trading_service.execute_trade(
                chat_id=chat_id,
                token=token,
                position_type=position_type,
                entry_price=None,
                quantity=amount if amount else None,
                leverage=2,
                stop_loss=None,
                take_profit=None
            )
            
            if result['success']:
                await event.reply(
                    f"✅ Trade executed successfully!\n\n"
                    f"📊 Token: {result['token']}\n"
                    f"📈 Position: {result['position_type'].upper()}\n"
                    f"💰 Entry Price: ${result['entry_price']:.2f}\n"
                    f"📦 Quantity: {result['quantity']:.6f}\n"
                    f"⚡ Leverage: {result['leverage']}x\n"
                    f"🛑 Stop Loss: ${result['stop_loss']:.2f}\n"
                    f"🎯 Take Profit: ${result['take_profit']:.2f}\n"
                    f"💵 Trade Value: ${result['trade_value']:.2f}"
                )
            else:
                await event.reply(f"❌ Trade failed: {result['error']}")
                
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(pattern=r'/positions'))
    async def on_positions(event):
        """Show open positions"""
        try:
            chat_id = event.chat_id
            positions = trading_service.get_user_positions(chat_id)
            
            if not positions:
                await event.reply("📊 No open positions.")
                return
            
            position_list = "\n\n".join([
                f"📊 Position #{pos.id}\n"
                f"Token: {pos.token}\n"
                f"Type: {pos.position_type.upper()}\n"
                f"Entry: ${pos.entry_price:.2f}\n"
                f"Quantity: {pos.quantity:.6f}\n"
                f"Leverage: {pos.leverage}x\n"
                f"Stop Loss: ${pos.stop_loss:.2f}\n"
                f"Take Profit: ${pos.take_profit:.2f}\n"
                f"PnL: ${pos.pnl:.2f}"
                for pos in positions
            ])
            
            await event.reply(f"📊 Open Positions:\n\n{position_list}")
        except Exception as e:
            logger.error(f"Error showing positions: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(pattern=r'/close'))
    async def on_close_position(event):
        """Close a position"""
        try:
            chat_id = event.chat_id
            message_text = event.message.message
            parts = message_text.split()
            
            if len(parts) < 2:
                await event.reply("Usage: /close <position_id>\nUse /positions to see your open positions.")
                return
            
            try:
                position_id = int(parts[1])
            except ValueError:
                await event.reply("❌ Invalid position ID. Please provide a valid number.")
                return
            
            result = trading_service.close_position(chat_id, position_id)
            
            if result['success']:
                await event.reply(
                    f"✅ Position closed!\n\n"
                    f"📊 Position ID: {result['position_id']}\n"
                    f"💵 Exit Price: ${result['exit_price']:.2f}\n"
                    f"💰 PnL: ${result['pnl']:.2f}\n"
                    f"Token: {result['token']}"
                )
            else:
                await event.reply(f"❌ Failed to close position: {result['error']}")
                
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(pattern=r'/history'))
    async def on_transaction_history(event):
        """Show transaction history"""
        try:
            chat_id = event.chat_id
            transactions = wallet_service.get_transaction_history(chat_id)
            
            if not transactions:
                await event.reply("📜 No transaction history.")
                return
            
            history_list = "\n\n".join([
                f"📝 Transaction #{tx.id}\n"
                f"Type: {tx.transaction_type.upper()}\n"
                f"Amount: ${tx.amount:.2f} {tx.currency}\n"
                f"Fee: ${tx.fee:.2f}\n"
                f"Status: {tx.status.upper()}\n"
                f"Date: {tx.created_at_utc}"
                for tx in transactions[:10]  # Show last 10 transactions
            ])
            
            await event.reply(f"📜 Transaction History (Last 10):\n\n{history_list}")
        except Exception as e:
            logger.error(f"Error showing history: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(pattern=r'/help'))
    async def on_help(event):
        """Show help message"""
        help_text = """
🤖 AI Trading Bot Commands

💼 Wallet Commands:
/create_wallet - Create a new custodial wallet
/wallet - Show wallet information and balance
/deposit - Show deposit instructions
/balance - Show current balance
/withdraw <amount> [currency] - Withdraw funds (7.5% fee)
/history - Show transaction history

📊 Trading Commands:
/trade <token> <long|short> [amount] - Execute AI-powered trade
/positions - Show open positions
/close <position_id> - Close a position

ℹ️ Other Commands:
/help - Show this help message

💡 Tips:
• The bot uses Mistral AI for market analysis
• All trades are executed internally (no external exchanges)
• 7.5% fee applies to all withdrawals
• Start with small amounts to test the system
        """
        await event.reply(help_text)
