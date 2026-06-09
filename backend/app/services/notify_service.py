"""
Multi-Channel Notification Service
Extends WhatsApp to Discord, Slack, Email, Telegram.

Channels:
1. Discord - Webhook
2. Slack - Bot + Webhook  
3. Email - SMTP with Markdown templates
4. Telegram - Bot API (already have)
5. WhatsApp - OpenWA (already have)

All channels support:
- Trade executions
- Trade closures (with PnL)
- Trading signals
- System alerts
- Risk warnings
"""
import httpx
import structlog
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List
from pathlib import Path
import json

logger = structlog.get_logger(__name__)


class MultiChannelNotifyService:
    """
    Multi-Channel Notification Service.
    
    Send notifications to:
    - Discord (webhook)
    - Slack (webhook or bot)
    - Email (SMTP)
    - Telegram (bot)
    - WhatsApp (OpenWA)
    
    All channels configured via settings page.
    """

    def __init__(self):
        self.config_file = Path("data/notify_config.json")
        self.config = self.load_config()
        logger.info("Multi-Channel Notify Service initialized")

    def load_config(self) -> Dict[str, Any]:
        """Load notification config"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {
            "discord": {"enabled": False, "webhook_url": ""},
            "slack": {"enabled": False, "webhook_url": ""},
            "email": {"enabled": False, "smtp_server": "", "smtp_port": 587, "username": "", "password": "", "from_email": "", "to_emails": []},
            "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
        }

    def save_config(self):
        """Save config to disk"""
        self.config_file.parent.mkdir(exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def configure_discord(self, webhook_url: str, enabled: bool = True):
        """Configure Discord webhook"""
        self.config["discord"] = {
            "enabled": enabled,
            "webhook_url": webhook_url,
        }
        self.save_config()
        logger.info(f"Discord configured: {enabled}")

    def configure_slack(self, webhook_url: str, enabled: bool = True):
        """Configure Slack webhook"""
        self.config["slack"] = {
            "enabled": enabled,
            "webhook_url": webhook_url,
        }
        self.save_config()
        logger.info(f"Slack configured: {enabled}")

    def configure_email(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: List[str],
        enabled: bool = True,
    ):
        """Configure Email SMTP"""
        self.config["email"] = {
            "enabled": enabled,
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "username": username,
            "password": password,
            "from_email": from_email,
            "to_emails": to_emails,
        }
        self.save_config()
        logger.info(f"Email configured: {enabled}")

    def configure_telegram(self, bot_token: str, chat_id: str, enabled: bool = True):
        """Configure Telegram bot"""
        self.config["telegram"] = {
            "enabled": enabled,
            "bot_token": bot_token,
            "chat_id": chat_id,
        }
        self.save_config()
        logger.info(f"Telegram configured: {enabled}")

    async def send_all_channels(self, title: str, message: str, embed_data: Optional[Dict] = None):
        """Send to all enabled channels"""
        tasks = []
        
        if self.config["discord"]["enabled"]:
            tasks.append(self.send_discord(title, message, embed_data))
        
        if self.config["slack"]["enabled"]:
            tasks.append(self.send_slack(title, message))
        
        if self.config["email"]["enabled"]:
            tasks.append(self.send_email(title, message))
        
        if self.config["telegram"]["enabled"]:
            tasks.append(self.send_telegram(title, message))
        
        if tasks:
            await asyncio.gather(*tasks)
        
        return {"channels_sent": len(tasks)}

    async def send_discord(self, title: str, message: str, embed_data: Optional[Dict] = None):
        """Send Discord embed notification"""
        if not self.config["discord"]["enabled"]:
            return False
        
        webhook_url = self.config["discord"]["webhook_url"]
        
        # Create embed
        embed = {
            "title": title,
            "description": message,
            "color": 5814783,  # Blue
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        
        if embed_data:
            embed.update(embed_data)
        
        payload = {
            "embeds": [embed],
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload)
                
                if response.status_code == 204:
                    logger.info("Discord notification sent")
                    return True
                else:
                    logger.error(f"Discord error: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Discord failed: {e}")
            return False

    async def send_slack(self, title: str, message: str):
        """Send Slack block notification"""
        if not self.config["slack"]["enabled"]:
            return False
        
        webhook_url = self.config["slack"]["webhook_url"]
        
        # Create blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title,
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message,
                }
            },
        ]
        
        payload = {
            "blocks": blocks,
            "text": title,  # Fallback
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload)
                
                if response.status_code == 200:
                    logger.info("Slack notification sent")
                    return True
                else:
                    logger.error(f"Slack error: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Slack failed: {e}")
            return False

    async def send_email(self, title: str, message: str, html: bool = True):
        """Send Email notification"""
        if not self.config["email"]["enabled"]:
            return False
        
        email_config = self.config["email"]
        to_emails = email_config["to_emails"]
        
        if not to_emails:
            logger.warning("Email: no recipients configured")
            return False
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Jasper Trades: {title}"
        msg["From"] = email_config["from_email"]
        msg["To"] = ", ".join(to_emails)
        
        # Plain text
        text = message
        msg.attach(MIMEText(text, "plain"))
        
        # HTML
        if html:
            html_message = f"""
            <html>
              <head>
                <style>
                  body {{ font-family: Arial, sans-serif; }}
                  .header {{ background: #2563eb; color: white; padding: 20px; }}
                  .content {{ padding: 20px; }}
                  .footer {{ background: #f3f4f6; padding: 10px; font-size: 12px; }}
                </style>
              </head>
              <body>
                <div class="header">
                  <h1>{title}</h1>
                </div>
                <div class="content">
                  {message.replace(chr(10), '<br>')}
                </div>
                <div class="footer">
                  Jasper Trades AI - Automated Trading System
                </div>
              </body>
            </html>
            """
            msg.attach(MIMEText(html_message, "html"))
        
        try:
            # Send via SMTP
            with smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"]) as server:
                server.starttls()
                server.login(email_config["username"], email_config["password"])
                server.send_message(msg)
            
            logger.info(f"Email sent to {len(to_emails)} recipients")
            return True
        except Exception as e:
            logger.error(f"Email failed: {e}")
            return False

    async def send_telegram(self, title: str, message: str):
        """Send Telegram notification"""
        if not self.config["telegram"]["enabled"]:
            return False
        
        bot_token = self.config["telegram"]["bot_token"]
        chat_id = self.config["telegram"]["chat_id"]
        
        text = f"*{title}*\n\n{message}"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    }
                )
                
                if response.status_code == 200:
                    logger.info("Telegram notification sent")
                    return True
                else:
                    logger.error(f"Telegram error: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Telegram failed: {e}")
            return False

    # Notification type helpers
    
    async def notify_trade_executed(self, trade: Dict):
        """Send trade execution to all channels"""
        title = "🔔 TRADE EXECUTED"
        message = (
            f"{trade.get('action', 'BUY')} {trade.get('shares', 0)} {trade.get('symbol', 'UNKNOWN')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: ${trade.get('price', 0):.2f}\n"
            f"💵 Total: ${trade.get('total', 0):.2f}\n"
            f"🤖 Agent: {trade.get('agent', 'AI')}\n"
            f"⏰ {trade.get('timestamp', 'Now')}"
        )
        
        embed_data = {
            "fields": [
                {"name": "Symbol", "value": trade.get("symbol", "N/A"), "inline": True},
                {"name": "Action", "value": trade.get("action", "N/A"), "inline": True},
                {"name": "Price", "value": f"${trade.get('price', 0):.2f}", "inline": True},
            ],
            "color": 3066993 if trade.get("action") == "BUY" else 15158332,
        }
        
        return await self.send_all_channels(title, message, embed_data)

    async def notify_trade_closed(self, trade: Dict):
        """Send trade closure with PnL"""
        pnl = trade.get('pnl', 0)
        pnl_percent = trade.get('pnl_percent', 0)
        
        if pnl > 0:
            emoji = "✅"
            color = 3066993  # Green
        elif pnl < 0:
            emoji = "❌"
            color = 15158332  # Red
        else:
            emoji = "➖"
            color = 9807270  # Gray
        
        title = f"{emoji} TRADE CLOSED - {'WIN' if pnl > 0 else 'LOSS' if pnl < 0 else 'BREAKEVEN'}"
        
        message = (
            f"{trade.get('action', 'SELL')} {trade.get('shares', 0)} {trade.get('symbol', 'UNKNOWN')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Entry: ${trade.get('entry_price', 0):.2f}\n"
            f"💰 Exit: ${trade.get('exit_price', 0):.2f}\n"
            f"📊 PnL: ${pnl:.2f} ({pnl_percent:+.2f}%)\n"
            f"⏱ Hold: {trade.get('hold_duration', 'N/A')}"
        )
        
        embed_data = {
            "fields": [
                {"name": "PnL", "value": f"${pnl:.2f}", "inline": True},
                {"name": "Return", "value": f"{pnl_percent:+.2f}%", "inline": True},
            ],
            "color": color,
        }
        
        return await self.send_all_channels(title, message, embed_data)

    async def notify_signal_generated(self, signal: Dict):
        """Send trading signal"""
        title = "📡 NEW SIGNAL"
        
        message = (
            f"{signal.get('action', 'BUY')} {signal.get('symbol', 'UNKNOWN')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Confidence: {signal.get('confidence', 0):.0%}\n"
            f"🎲 Model: {signal.get('model', 'AI')}\n"
            f"📝 Reason: {signal.get('reason', 'N/A')[:100]}"
        )
        
        embed_data = {
            "color": 15844367,  # Yellow
        }
        
        return await self.send_all_channels(title, message, embed_data)

    async def notify_risk_alert(self, alert_type: str, details: Dict):
        """Send risk alert"""
        title = f"⚠️ RISK ALERT: {alert_type}"
        
        message = "\n".join([f"{k}: {v}" for k, v in details.items()])
        
        embed_data = {
            "color": 15158332,  # Red
            "footer": {"text": "Circuit Breaker System"},
        }
        
        return await self.send_all_channels(title, message, embed_data)

    async def notify_withdrawal_requested(self, withdrawal: Any):
        """Send notification when withdrawal is requested."""
        from app.models import Withdrawal
        
        title = "💰 WITHDRAWAL REQUESTED"
        
        withdrawal_type = getattr(withdrawal, 'withdrawal_type', 'manual')
        type_label = "Auto-Payout" if withdrawal_type == "auto_payout" else "Manual"
        
        message = (
            f"{type_label} Withdrawal\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Amount: ${getattr(withdrawal, 'amount', 0):.2f}\n"
            f"💸 Fee: ${getattr(withdrawal, 'fee', 0):.2f}\n"
            f"✅ Net: ${getattr(withdrawal, 'net_amount', 0):.2f}\n"
            f"🎯 Destination: {getattr(withdrawal, 'destination_type', 'N/A')}\n"
            f"⏳ Status: {getattr(withdrawal, 'status', 'pending')}"
        )
        
        embed_data = {
            "color": 15844367,  # Yellow (pending)
            "fields": [
                {"name": "Amount", "value": f"${getattr(withdrawal, 'amount', 0):.2f}"},
                {"name": "Net", "value": f"${getattr(withdrawal, 'net_amount', 0):.2f}"},
            ],
        }
        
        return await self.send_all_channels(title, message, embed_data)

    async def notify_withdrawal_completed(self, withdrawal: Any):
        """Send notification when withdrawal is completed."""
        from app.models import Withdrawal
        
        withdrawal_type = getattr(withdrawal, 'withdrawal_type', 'manual')
        type_label = "Auto-Payout" if withdrawal_type == "auto_payout" else "Withdrawal"
        
        tx_hash = getattr(withdrawal, 'transaction_hash', '')
        tx_short = tx_hash[:10] + "..." + tx_hash[-5:] if tx_hash else "N/A"
        
        # Check if it's an auto-payout with profit info
        daily_pnl = getattr(withdrawal, 'daily_pnl', None)
        payout_pct = getattr(withdrawal, 'payout_percentage', 50.0)
        
        if daily_pnl:
            message = (
                f"🎉 Auto-Payout Executed\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 Daily Profit: ${daily_pnl:.2f}\n"
                f"💰 Payout ({payout_pct}%): ${getattr(withdrawal, 'amount', 0):.2f}\n"
                f"💸 Fee: ${getattr(withdrawal, 'fee', 0):.2f}\n"
                f"✅ Net Sent: ${getattr(withdrawal, 'net_amount', 0):.2f}\n"
                f"🎯 Destination: {getattr(withdrawal, 'destination_address', 'N/A')[:20]}...\n"
                f"🔗 Tx Hash: `{tx_short}`"
            )
        else:
            message = (
                f"✅ WITHDRAWAL COMPLETED\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 Amount: ${getattr(withdrawal, 'amount', 0):.2f}\n"
                f"💸 Fee: ${getattr(withdrawal, 'fee', 0):.2f}\n"
                f"✅ Net Sent: ${getattr(withdrawal, 'net_amount', 0):.2f}\n"
                f"🔗 Tx Hash: `{tx_short}`"
            )
        
        embed_data = {
            "color": 5763719,  # Green
            "fields": [
                {"name": "Amount", "value": f"${getattr(withdrawal, 'amount', 0):.2f}"},
                {"name": "Net", "value": f"${getattr(withdrawal, 'net_amount', 0):.2f}"},
            ],
        }
        
        return await self.send_all_channels("💰 " + type_label + " COMPLETED", message, embed_data)

    async def notify_withdrawal_failed(self, withdrawal: Any, error: str):
        """Send notification when withdrawal fails."""
        title = "❌ WITHDRAWAL FAILED"
        
        message = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Amount: ${getattr(withdrawal, 'amount', 0):.2f}\n"
            f"⚠️ Error: {error}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Please contact support or try again."
        )
        
        embed_data = {
            "color": 15158332,  # Red
        }
        
        return await self.send_all_channels(title, message, embed_data)

    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "channels": {
                "discord": {
                    "enabled": self.config["discord"]["enabled"],
                    "configured": bool(self.config["discord"]["webhook_url"]),
                },
                "slack": {
                    "enabled": self.config["slack"]["enabled"],
                    "configured": bool(self.config["slack"]["webhook_url"]),
                },
                "email": {
                    "enabled": self.config["email"]["enabled"],
                    "configured": bool(self.config["email"]["smtp_server"]) and bool(self.config["email"]["to_emails"]),
                    "recipients": len(self.config["email"]["to_emails"]),
                },
                "telegram": {
                    "enabled": self.config["telegram"]["enabled"],
                    "configured": bool(self.config["telegram"]["bot_token"]) and bool(self.config["telegram"]["chat_id"]),
                },
            },
            "total_channels": sum(1 for c in self.config.values() if c.get("enabled")),
        }


# Import for async
import asyncio
from datetime import datetime

# Singleton instance
notify_service = MultiChannelNotifyService()