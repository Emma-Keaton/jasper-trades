"""
Email Service - SendGrid Integration

SendGrid FREE tier: 100 emails/day forever
Perfect for trade notifications, alerts, and reports.

Configuration via Settings page:
- API key (encrypted)
- From email
- Enabled/disabled toggle
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class SendGridService:
    """SendGrid email service for notifications."""

    def __init__(self):
        self.api_key = None
        self.from_email = None
        self.enabled = False

    def configure(self, config: Dict[str, Any]):
        """Configure SendGrid from settings."""
        self.api_key = config.get('api_key')
        self.from_email = config.get('from_email')
        self.enabled = config.get('enabled', False)
        
        if self.api_key and self.from_email:
            logger.info("SendGrid configured", from_email=self.from_email)
        else:
            logger.warning("SendGrid not fully configured")

    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        content: str,
        content_type: str = 'text/plain',
        html: bool = False
    ) -> Dict[str, Any]:
        """
        Send email via SendGrid.
        
        Args:
            to_emails: List of recipient emails
            subject: Email subject
            content: Email body
            content_type: 'text/plain' or 'text/html'
            html: If True, content is HTML
        
        Returns:
            SendGrid response or error
        """
        if not self.enabled:
            return {'success': False, 'error': 'SendGrid not enabled'}

        if not self.api_key:
            return {'success': False, 'error': 'SendGrid API key not configured'}

        if not self.from_email:
            return {'success': False, 'error': 'From email not configured'}

        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content

            sg = sendgrid.SendGridAPIClient(api_key=self.api_key)

            # Create email object
            from_email = Email(self.from_email)
            
            # Handle multiple recipients
            to_emails_list = [To(email) for email in to_emails]
            
            content_type = 'text/html' if html else 'text/plain'
            content = Content(content_type, content)

            # Build subject (truncate if too long)
            subject_truncated = subject[:998] if len(subject) > 998 else subject

            mail = Mail(from_email, to_emails_list, subject_truncated, content)

            # Send
            response = await asyncio.get_event_loop().run_in_executor(
                None, sg.send, mail
            )

            logger.info(f"SendGrid email sent to {len(to_emails)} recipients", 
                       status_code=response.status_code)

            return {
                'success': True,
                'message_id': response.headers.get('X-Message-Id'),
                'status_code': response.status_code,
            }

        except ImportError:
            logger.error("sendgrid package not installed. Run: pip install sendgrid")
            return {
                'success': False,
                'error': 'SendGrid library not installed. Run: pip install sendgrid'
            }
        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return {'success': False, 'error': str(e)}

    async def send_trade_notification(
        self,
        to_emails: List[str],
        symbol: str,
        action: str,  # BUY or SELL
        quantity: float,
        price: float,
        agent_name: str = "Jasper AI"
    ) -> Dict[str, Any]:
        """Send trade execution notification."""
        subject = f"📈 Trade Executed: {action} {symbol}"
        
        content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2 style="color: {'#10B981' if action == 'BUY' else '#EF4444'};">
                {action} Order Executed
            </h2>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Symbol</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{symbol}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Action</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{action}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Quantity</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{quantity}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Price</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${price:,.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Total Value</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${quantity * price:,.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Executed by</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{agent_name}</td>
                </tr>
            </table>
            
            <p style="color: #6B7280; font-size: 12px; margin-top: 20px;">
                Sent by Jasper Trades AI
            </p>
        </body>
        </html>
        """

        return await self.send_email(to_emails, subject, content, html=True)

    async def send_price_alert(
        self,
        to_emails: List[str],
        symbol: str,
        target_price: float,
        current_price: float,
        alert_type: str  # 'above' or 'below'
    ) -> Dict[str, Any]:
        """Send price alert notification."""
        direction = "above" if alert_type == 'above' else "below"
        subject = f"🔔 Price Alert: {symbol} {direction} ${target_price:,.2f}"
        
        content = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #3B82F6;">Price Alert Triggered</h2>
            
            <p><strong>{symbol}</strong> has moved {direction} your target price!</p>
            
            <table style="width: 100%; margin: 20px 0;">
                <tr>
                    <td>Target Price:</td>
                    <td><strong>${target_price:,.2f}</strong></td>
                </tr>
                <tr>
                    <td>Current Price:</td>
                    <td><strong>${current_price:,.2f}</strong></td>
                </tr>
                <tr>
                    <td>Difference:</td>
                    <td><strong>${current_price - target_price:,.2f} ({((current_price - target_price) / target_price * 100):.2f}%)</strong></td>
                </tr>
            </table>
            
            <p style="color: #6B7280; font-size: 12px;">
                Jasper Trades Price Alert
            </p>
        </body>
        </html>
        """

        return await self.send_email(to_emails, subject, content, html=True)

    async def send_daily_summary(
        self,
        to_emails: List[str],
        pnl: float,
        trades_count: int,
        win_rate: float,
        portfolio_value: float
    ) -> Dict[str, Any]:
        """Send daily trading summary."""
        subject = f"📊 Daily Trading Summary - PnL: ${pnl:,.2f}"
        
        pnl_color = '#10B981' if pnl >= 0 else '#EF4444'
        
        content = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #3B82F6;">Daily Trading Summary</h2>
            
            <div style="background: {pnl_color}; color: white; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                <div style="font-size: 32px; font-weight: bold;">${pnl:,.2f}</div>
                <div>Today's P&L</div>
            </div>
            
            <table style="width: 100%; margin: 20px 0;">
                <tr>
                    <td>Portfolio Value:</td>
                    <td><strong>${portfolio_value:,.2f}</strong></td>
                </tr>
                <tr>
                    <td>Trades Executed:</td>
                    <td><strong>{trades_count}</strong></td>
                </tr>
                <tr>
                    <td>Win Rate:</td>
                    <td><strong>{win_rate:.1f}%</strong></td>
                </tr>
            </table>
            
            <p style="color: #6B7280; font-size: 12px;">
                Thank you for using Jasper Trades!
            </p>
        </body>
        </html>
        """

        return await self.send_email(to_emails, subject, content, html=True)


# Singleton
_sendgrid_service: Optional[SendGridService] = None


def get_sendgrid_service() -> SendGridService:
    """Get SendGrid service singleton."""
    global _sendgrid_service
    if _sendgrid_service is None:
        _sendgrid_service = SendGridService()
    return _sendgrid_service


# Note: Install sendgrid with: pip install sendgrid