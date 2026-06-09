"""
Enhanced Discord Bot Service - Two-Way Chat

Unlike webhooks (send-only), the Discord bot supports:
- Receiving commands from Discord
- Sending responses back
- Real-time notifications
- Trade Q&A via AI

FREE to set up at https://discord.com/developers/applications
"""
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import structlog
import asyncio

logger = structlog.get_logger(__name__)


class DiscordBotService:
    """Two-way Discord bot for chat and notifications."""

    def __init__(self):
        self.bot = None
        self.is_running = False
        self.config = {
            'bot_token': None,
            'guild_id': None,  # Server ID
            'channel_id': None,  # Main channel ID
            'enabled': False,
            'chat_enabled': False,
        }
        self.command_handlers: Dict[str, Callable] = {}
        self._register_default_commands()

    def _register_default_commands(self):
        """Register default AI chat commands."""
        self.command_handlers['portfolio'] = self._handle_portfolio_command
        self.command_handlers['trades'] = self._handle_trades_command
        self.command_handlers['help'] = self._handle_help_command
        self.command_handlers['status'] = self._handle_status_command

    def configure(self, config: Dict[str, Any]):
        """Configure bot from settings."""
        self.config.update(config)
        
        if config.get('bot_token'):
            logger.info("Discord bot configured", 
                       guild_id=config.get('guild_id'),
                       channel_id=config.get('channel_id'))
        else:
            logger.warning("Discord bot not configured")

    async def start(self) -> bool:
        """Start Discord bot."""
        if not self.config.get('bot_token'):
            logger.warning("Discord bot token not configured")
            return False

        if self.is_running:
            logger.info("Discord bot already running")
            return True

        try:
            # Check if discord.py is installed
            import discord
            from discord.ext import commands

            # Create bot
            intents = discord.Intents.default()
            intents.message_content = True  # For reading commands
            self.bot = commands.Bot(command_prefix='!', intents=intents)

            # Event: Bot ready
            @self.bot.event
            async def on_ready():
                logger.info(f"Discord bot logged in as {self.bot.user}")
                self.is_running = True

            # Event: Message received
            @self.bot.event
            async def on_message(message):
                # Ignore bot's own messages
                if message.author == self.bot.user:
                    return

                # Only respond in configured channel
                if self.config.get('channel_id') and str(message.channel.id) != str(self.config['channel_id']):
                    return

                # Check for command
                if message.content.startswith('!'):
                    cmd = message.content[1:].strip().lower()
                    
                    # Handle commands
                    for cmd_name, handler in self.command_handlers.items():
                        if cmd.startswith(cmd_name):
                            response = await handler(cmd, message)
                            if response:
                                await message.channel.send(response)
                            return

                    # Unknown command
                    await message.channel.send(
                        f"❓ Unknown command. Type `!help` for available commands."
                    )

            # Start bot in background
            asyncio.create_task(self.bot.start(self.config['bot_token']))
            
            # Wait for bot to connect
            await asyncio.sleep(3)
            
            logger.info("Discord bot started successfully")
            return True

        except ImportError:
            logger.error("discord.py not installed. Run: pip install discord.py")
            return False
        except Exception as e:
            logger.error(f"Discord bot start error: {e}")
            return False

    async def stop(self):
        """Stop Discord bot."""
        if self.bot and self.is_running:
            await self.bot.close()
            self.is_running = False
            logger.info("Discord bot stopped")

    async def send_message(self, content: str, channel_id: str = None) -> Dict[str, Any]:
        """Send message to Discord channel."""
        if not self.is_running:
            return {'success': False, 'error': 'Bot not running'}

        try:
            target_channel_id = channel_id or self.config.get('channel_id')
            if not target_channel_id:
                return {'success': False, 'error': 'Channel ID not configured'}

            channel = self.bot.get_channel(int(target_channel_id))
            if not channel:
                return {'success': False, 'error': 'Channel not found'}

            await channel.send(content)
            logger.info(f"Discord message sent: {content[:50]}...")
            
            return {'success': True}

        except Exception as e:
            logger.error(f"Discord send error: {e}")
            return {'success': False, 'error': str(e)}

    async def send_trade_notification(self, symbol: str, action: str, quantity: float, price: float) -> Dict[str, Any]:
        """Send formatted trade notification embed."""
        color = 0x10B981 if action == 'BUY' else 0xEF4444
        
        import discord
        embed = discord.Embed(
            title=f"{'🟢' if action == 'BUY' else '🔴'} Trade Executed",
            description=f"{action} **{symbol}**",
            color=color
        )
        embed.add_field(name="Quantity", value=f"{quantity}", inline=True)
        embed.add_field(name="Price", value=f"${price:,.2f}", inline=True)
        embed.add_field(name="Total", value=f"${quantity * price:,.2f}", inline=True)
        embed.set_footer(text="Jasper Trades AI")

        return await self.send_message(embed=embed)

    # ============ Command Handlers ============

    async def _handle_portfolio_command(self, cmd: str, message) -> Optional[str]:
        """Handle !portfolio command."""
        # This would fetch portfolio data from backend
        # For now, return placeholder
        return """
        📊 **Portfolio Summary**
        
        💰 Total Value: $100,000.00
        💵 Cash: $50,000.00
        📈 Invested: $50,000.00
        ✅ Today's PnL: +$1,234.56 (+1.2%)
        
        Type `!trades` for recent trades.
        """

    async def _handle_trades_command(self, cmd: str, message) -> Optional[str]:
        """Handle !trades command."""
        return """
        📊 **Recent Trades (Today)**
        
        1. ✅ BUY AAPL 10 @ $150.00
        2. ✅ SELL TSLA 5 @ $250.00
        3. ✅ BUY NVDA 20 @ $450.00
        
        Type `!help` for more commands.
        """

    async def _handle_help_command(self, cmd: str, message) -> Optional[str]:
        """Handle !help command."""
        return """
        🤖 **Jasper Trades Bot Commands**
        
        📊 `!portfolio` - View portfolio summary
        📊 `!trades` - Recent trades
        📊 `!status` - Bot status
        📊 `!help` - This help message
        
        💬 Ask questions like:
        - "Should I buy AAPL?"
        - "What's your outlook on NVDA?"
        
        More features coming soon!
        """

    async def _handle_status_command(self, cmd: str, message) -> Optional[str]:
        """Handle !status command."""
        return f"""
        ✅ **Bot Status: Online**
        
        Guild ID: {self.config.get('guild_id', 'N/A')}
        Channel ID: {self.config.get('channel_id', 'N/A')}
        Uptime: Running since startup
        
        Jasper Trades Bot v1.0
        """

    def get_status(self) -> Dict[str, Any]:
        """Get bot status."""
        return {
            'running': self.is_running,
            'configured': bool(self.config.get('bot_token')),
            'guild_id': self.config.get('guild_id'),
            'channel_id': self.config.get('channel_id'),
            'chat_enabled': self.config.get('chat_enabled'),
        }


# Singleton
_discord_bot_service: Optional[DiscordBotService] = None


def get_discord_bot_service() -> DiscordBotService:
    """Get Discord bot service singleton."""
    global _discord_bot_service
    if _discord_bot_service is None:
        _discord_bot_service = DiscordBotService()
    return _discord_bot_service


# Note: Install discord.py with: pip install discord.py