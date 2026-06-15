"""
WhatsApp Notification Service using OpenWA
Sends trade notifications to user's phone via WhatsApp

All messages are sent from "Jasper Trades"
"""
import httpx
import structlog
from typing import Optional, Dict, List
from pathlib import Path
import json
from datetime import datetime

from app.services.whatsapp_templates import (
    format_trade_executed,
    format_trade_closed,
    format_daily_summary,
    format_portfolio_summary,
    format_positions_list,
    format_recent_trades,
    format_welcome_message,
    format_verification_code,
)

logger = structlog.get_logger(__name__)


class WhatsAppService:
    """
    WhatsApp notification service using local OpenWA instance.
    Connects to OpenWA running on localhost:3001 (default OpenWA port)
    
    Setup: https://github.com/rmyndharis/OpenWA
    """
    
    def __init__(self):
        self.openwa_url = "http://localhost:3001"  # Default OpenWA port
        self.enabled = False
        self.phone_number = ""
        self.session_file = Path("data/whatsapp_config.json")
        self.load_config()
        logger.info(f"WhatsApp Service initialized (enabled: {self.enabled})")
    
    def load_config(self):
        """Load WhatsApp config from disk"""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    config = json.load(f)
                    self.enabled = config.get("enabled", False)
                    self.phone_number = config.get("phone_number", "")
                    self.openwa_url = config.get("openwa_url", "http://localhost:3001")
            except Exception as e:
                logger.error(f"Failed to load WhatsApp config: {e}")
    
    def save_config(self):
        """Save WhatsApp config to disk"""
        self.session_file.parent.mkdir(exist_ok=True)
        config = {
            "enabled": self.enabled,
            "phone_number": self.phone_number,
            "openwa_url": self.openwa_url
        }
        with open(self.session_file, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("WhatsApp config saved")
    
    def configure(self, phone_number: str, enabled: bool = True, openwa_url: str = None):
        """Configure WhatsApp notifications"""
        self.phone_number = phone_number
        self.enabled = enabled
        if openwa_url:
            self.openwa_url = openwa_url
        self.save_config()
    
    def format_number(self, phone: str) -> str:
        """Format phone number for WhatsApp (remove +, spaces, dashes)"""
        cleaned = ''.join(c for c in phone if c.isdigit())
        # If starts with 0, remove it (e.g., 09123 → 9123)
        if cleaned.startswith('0'):
            cleaned = cleaned[1:]
        return cleaned
    
    async def send_message(self, message: str, title: str = None) -> bool:
        """Send WhatsApp message to configured phone number"""
        if not self.enabled or not self.phone_number:
            logger.debug("WhatsApp notifications disabled or no phone configured")
            return False
        
        try:
            # Format message with title if provided
            if title:
                full_message = f"*{title}*\n\n{message}"
            else:
                full_message = message
            
            # Send to OpenWA
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.openwa_url}/api/send",
                    json={
                        "phone": self.format_number(self.phone_number),
                        "message": full_message,
                        "type": "text"
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"WhatsApp sent to {self.phone_number}")
                    return True
                else:
                    logger.error(f"WhatsApp API error: {response.status_code} - {response.text}")
                    return False
                    
        except httpx.ConnectError as e:
            logger.warning(f"OpenWA not reachable at {self.openwa_url}: {e}")
            return False
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            return False
    
    async def notify_trade_executed(self, trade: Dict) -> bool:
        """Send trade execution notification"""
        title = "🔔 TRADE EXECUTED"
        
        message = (
            f"{trade.get('action', 'BUY')} {trade.get('shares', 0)} {trade.get('symbol', 'UNKNOWN')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: ${trade.get('price', 0):.2f}\n"
            f"💵 Total: ${trade.get('total', 0):.2f}\n"
            f"🤖 Agent: {trade.get('agent', 'AI')}\n"
            f"📈 Type: {trade.get('order_type', 'MARKET')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {trade.get('timestamp', 'Now')}"
        )
        
        return await self.send_message(message, title)
    
    async def notify_trade_closed(self, trade: Dict) -> bool:
        """Send trade closed/notification with PnL"""
        pnl = trade.get('pnl', 0)
        pnl_percent = trade.get('pnl_percent', 0)
        
        # Color based on outcome
        if pnl > 0:
            emoji = "✅"
            outcome = "WIN"
        elif pnl < 0:
            emoji = "❌"
            outcome = "LOSS"
        else:
            emoji = "➖"
            outcome = "BREAKEVEN"
        
        title = f"{emoji} TRADE CLOSED - {outcome}"
        
        message = (
            f"{trade.get('action', 'SELL')} {trade.get('shares', 0)} {trade.get('symbol', 'UNKNOWN')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Entry: ${trade.get('entry_price', 0):.2f}\n"
            f"💰 Exit: ${trade.get('exit_price', 0):.2f}\n"
            f"📊 PnL: ${pnl:.2f} ({pnl_percent:+.2f}%)\n"
            f"⏱ Hold: {trade.get('hold_duration', 'N/A')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {trade.get('timestamp', 'Now')}"
        )
        
        return await self.send_message(message, title)
    
    async def notify_signal_generated(self, signal: Dict) -> bool:
        """Send new trading signal notification"""
        title = "📡 NEW SIGNAL"
        
        message = (
            f"{signal.get('action', 'BUY')} {signal.get('symbol', 'UNKNOWN')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Confidence: {signal.get('confidence', 0):.0%}\n"
            f"🎲 Model: {signal.get('model', 'AI')}\n"
            f"📝 Reason: {signal.get('reason', 'N/A')[:100]}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {signal.get('timestamp', 'Now')}"
        )
        
        return await self.send_message(message, title)
    
    async def notify_system_alert(self, title: str, message: str) -> bool:
        """Send system alert (low balance, agent error, etc.)"""
        return await self.send_message(message, f"⚠️ {title}")
    
    async def send_trade_notification(self, trade_data: Dict) -> bool:
        """Send trade execution notification using template."""
        formatted_message = format_trade_executed(trade_data)
        return await self.send_message(formatted_message)
    
    async def send_trade_closure(self, trade_data: Dict) -> bool:
        """Send trade closure notification using template."""
        formatted_message = format_trade_closed(trade_data)
        return await self.send_message(formatted_message)
    
    async def send_daily_summary(self, summary_data: Dict) -> bool:
        """Send daily summary notification using template."""
        formatted_message = format_daily_summary(summary_data)
        return await self.send_message(formatted_message)
    
    async def send_portfolio_update(self, phone_number: str, summary_data: Dict) -> bool:
        """Send portfolio update to specific phone number."""
        # Temporarily override phone number
        original_phone = self.phone_number
        self.phone_number = phone_number
        
        formatted_message = format_portfolio_summary(summary_data)
        success = await self.send_message(formatted_message)
        
        # Restore original
        self.phone_number = original_phone
        return success
    
    async def send_positions_list(self, phone_number: str, positions: List[Dict]) -> bool:
        """Send positions list to specific phone number."""
        original_phone = self.phone_number
        self.phone_number = phone_number
        
        formatted_message = format_positions_list(positions)
        success = await self.send_message(formatted_message)
        
        self.phone_number = original_phone
        return success
    
    async def send_recent_trades(self, phone_number: str, trades: List[Dict]) -> bool:
        """Send recent trades to specific phone number."""
        original_phone = self.phone_number
        self.phone_number = phone_number
        
        formatted_message = format_recent_trades(trades)
        success = await self.send_message(formatted_message)
        
        self.phone_number = original_phone
        return success
    
    async def send_welcome_message(self, phone_number: str, summary_time: str = "8:00 PM WAT") -> bool:
        """Send welcome message when user first connects."""
        original_phone = self.phone_number
        self.phone_number = phone_number
        
        formatted_message = format_welcome_message(summary_time)
        success = await self.send_message(formatted_message)
        
        self.phone_number = original_phone
        return success
    
    async def send_verification_code(self, phone_number: str, code: str, expires_minutes: int = 10) -> bool:
        """Send verification code for phone number verification."""
        original_phone = self.phone_number
        self.phone_number = phone_number
        
        formatted_message = format_verification_code(code, expires_minutes)
        success = await self.send_message(formatted_message)
        
        self.phone_number = original_phone
        return success

    async def test_connection(self) -> bool:
        """Test WhatsApp connection with a test message"""
        test_message = (
            "🔊 *Jasper Trades Test*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✅ WhatsApp notifications are working!\n\n"
            "You will now receive:\n"
            "• Trade executions\n"
            "• Trade closures (with PnL)\n"
            "• Trading signals\n"
            "• System alerts\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 Jasper Trades AI"
        )
        
        success = await self.send_message(test_message)
        
        if success:
            logger.info("WhatsApp test message sent successfully")
        else:
            logger.warning("WhatsApp test message failed")
        
        return success
    
    def get_status(self) -> Dict:
        """Get WhatsApp service status"""
        return {
            "enabled": self.enabled,
            "phone_number": self.phone_number[:5] + "***" if self.phone_number else "",
            "openwa_url": self.openwa_url,
            "configured": bool(self.phone_number) and self.enabled
        }


# Singleton instance
whatsapp_service = WhatsAppService()