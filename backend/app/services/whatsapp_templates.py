"""
WhatsApp Message Templates
Standardized, branded message formats for different notification types
All messages sent from "Jasper Trades"
"""

# Trade Execution Template
TRADE_EXECUTED_TEMPLATE = """
🔔 *TRADE EXECUTED*
━━━━━━━━━━━━━━━━━━━━
📈 {action} {shares} {symbol}
💰 Price: ${price:.2f}
💵 Total: ${total:.2f}
🤖 Agent: {agent_name}
🎯 Strategy: {strategy}
⏰ {timestamp}
━━━━━━━━━━━━━━━━━━━━
Reply *INFO {symbol}* for details
"""

# Daily Summary Template
DAILY_SUMMARY_TEMPLATE = """
{emoji} *DAILY SUMMARY - {outcome}*
━━━━━━━━━━━━━━━━━━━━
📅 {date}

💰 **Total PnL:** ${total_pnl:+,.2f}
📈 **Return:** {total_pnl_percent:+.2f}%
📊 **Win Rate:** {win_rate:.1f}% ({wins}W / {losses}L / {breakeven}BE)
🎯 **Trades:** {total_trades}

🏆 *Best Trade:*
  {best_trade_text}

📉 *Worst Trade:*
  {worst_trade_text}

🤖 *Agent Performance:*
{agent_stats_text}
━━━━━━━━━━━━━━━━━━━━
📊 Type *STATUS* for portfolio
📈 Type *TRADES* for today's trades
💬 Type *HELP* for commands
"""

# Trade Closure with PnL
TRADE_CLOSED_TEMPLATE = """
{emoji} *{outcome}* - {symbol}
━━━━━━━━━━━━━━━━━━━━
💰 Entry: ${entry_price:.2f}
💰 Exit: ${exit_price:.2f}
📊 **PnL:** ${pnl:+,.2f} ({pnl_percent:+.2f}%)
⏱ Hold: {hold_duration}
━━━━━━━━━━━━━━━━━━━━
Reply *WHY* to see AI reasoning
"""

# AI Signal/Recommendation
AI_SIGNAL_TEMPLATE = """
📡 *NEW SIGNAL* - {symbol}
━━━━━━━━━━━━━━━━━━━━
🎯 Action: {action}
📊 Confidence: {confidence:.0%}
🧠 Model: {model_name}
📝 Reason: {reasoning}
━━━━━━━━━━━━━━━━━━━━
Reply *ACTIVATE* to enable this signal
"""

# Risk Alert
RISK_ALERT_TEMPLATE = """
⚠️ *RISK ALERT*
━━━━━━━━━━━━━━━━━━━━
🚨 {alert_type}
📊 Metric: {metric_name}
⚡ Current: {current_value}
🔴 Threshold: {threshold_value}
━━━━━━━━━━━━━━━━━━━━
{action_message}
"""

# Market Status
MARKET_STATUS_TEMPLATE = """
🕐 *MARKET STATUS*
━━━━━━━━━━━━━━━━━━━━
🇺🇸 US Market: {status}
📊 Next: {next_event}
⏰ Time: {time}
━━━━━━━━━━━━━━━━━━━━
Crypto: 24/7 | Forex: Sun 5PM - Fri 5PM ET
"""

# Portfolio Query Response
PORTFOLIO_SUMMARY_TEMPLATE = """
📊 *PORTFOLIO SUMMARY*
━━━━━━━━━━━━━━━━━━━━
💰 Value: ${total_value:,.2f}
💵 Cash: ${cash:,.2f}
📈 Holdings: ${market_value:,.2f}
📊 Return: ${return_value:+,.2f} ({return_pct:+.2f}%)
━━━━━━━━━━━━━━━━━━━━
Positions: {positions_count}
Type: {paper_or_live}
"""

# Positions List
POSITIONS_LIST_TEMPLATE = """
📊 *CURRENT POSITIONS*
━━━━━━━━━━━━━━━━━━━━
{positions_list}
━━━━━━━━━━━━━━━━━━━━
Total: {positions_count} positions
"""

# Recent Trades
RECENT_TRADES_TEMPLATE = """
📜 *RECENT TRADES*
━━━━━━━━━━━━━━━━━━━━
{trades_list}
━━━━━━━━━━━━━━━━━━━━
Total: {total_trades} trades today
"""

# Welcome Message (when user first connects WhatsApp)
WELCOME_MESSAGE_TEMPLATE = """
🎉 *Welcome to Jasper Trades!*
━━━━━━━━━━━━━━━━━━━━
Your WhatsApp is now connected to your Jasper Trades portfolio.

You'll receive:
✅ Real-time trade executions
✅ Trade closures with PnL
✅ Daily summary at {summary_time}
✅ Risk alerts & system notifications

💬 *Chat Commands:*
• STATUS - Portfolio overview
• POSITIONS - Current holdings
• TRADES - Today's trades
• HELP - All commands

🤖 Jasper Trades AI
"""

# Verification Code (for phone number verification)
VERIFICATION_CODE_TEMPLATE = """
🔐 *Jasper Trades Verification*
━━━━━━━━━━━━━━━━━━━━
Your verification code: *{code}*

Enter this code in the Settings page to complete WhatsApp verification.

Code expires in {expires_minutes} minutes.
"""

# System Alert
SYSTEM_ALERT_TEMPLATE = """
⚠️ *SYSTEM ALERT*
━━━━━━━━━━━━━━━━━━━━
{alert_message}
━━━━━━━━━━━━━━━━━━━━
⏰ {timestamp}
"""

# Position Update (significant price movement)
POSITION_UPDATE_TEMPLATE = """
📈 *POSITION UPDATE* - {symbol}
━━━━━━━━━━━━━━━━━━━━
💰 Current Price: ${price:.2f}
📊 Change: {change:+.2f}%
💵 PnL: ${pnl:+,.2f} ({pnl_percent:+.2f}%)
━━━━━━━━━━━━━━━━━━━━
Qty: {quantity} | Avg: ${avg_price:.2f}
"""

# Weekly Summary (extended version of daily)
WEEKLY_SUMMARY_TEMPLATE = """
📊 *WEEKLY SUMMARY*
━━━━━━━━━━━━━━━━━━━━
📅 Week of {week_start} - {week_end}

💰 **Total PnL:** ${total_pnl:+,.2f}
📈 **Return:** {total_pnl_percent:+.2f}%
📊 **Win Rate:** {win_rate:.1f}% ({wins}W / {losses}L)
🎯 **Trades:** {total_trades}

🏆 *Best Week:*
  {best_trade_text}

📉 *Worst Week:*
  {worst_trade_text}

🤖 *Top Agents:*
{agent_stats_text}
━━━━━━━━━━━━━━━━━━━━
Type *DETAILS* for full breakdown
"""

# Monthly Performance
MONTHLY_SUMMARY_TEMPLATE = """
📊 *MONTHLY PERFORMANCE*
━━━━━━━━━━━━━━━━━━━━
📅 {month_name} {year}

💰 **Total PnL:** ${total_pnl:+,.2f}
📈 **Return:** {total_pnl_percent:+.2f}%
📊 **Win Rate:** {win_rate:.1f}%
🎯 **Trades:** {total_trades}

🏆 *Best Trade:*
  {best_trade_text}

📉 *Worst Trade:*
  {worst_trade_text}

🤖 *Agent Performance:*
{agent_stats_text}
━━━━━━━━━━━━━━━━━━━━
Type *REPORT* for PDF summary
"""


def format_trade_executed(trade_data: dict) -> str:
    """Format trade execution message."""
    return TRADE_EXECUTED_TEMPLATE.format(
        action=trade_data.get('action', 'BUY'),
        shares=trade_data.get('shares', 0),
        symbol=trade_data.get('symbol', 'UNKNOWN'),
        price=trade_data.get('price', 0),
        total=trade_data.get('total', 0),
        agent_name=trade_data.get('agent_name', 'AI'),
        strategy=trade_data.get('strategy', 'Market'),
        timestamp=trade_data.get('timestamp', 'Now'),
    )


def format_trade_closed(trade_data: dict) -> str:
    """Format trade closure message."""
    pnl = trade_data.get('pnl', 0)
    pnl_percent = trade_data.get('pnl_percent', 0)
    
    if pnl > 0:
        emoji = "✅"
        outcome = "WIN"
    elif pnl < 0:
        emoji = "❌"
        outcome = "LOSS"
    else:
        emoji = "➖"
        outcome = "BREAKEVEN"
    
    return TRADE_CLOSED_TEMPLATE.format(
        emoji=emoji,
        outcome=outcome,
        symbol=trade_data.get('symbol', 'UNKNOWN'),
        entry_price=trade_data.get('entry_price', 0),
        exit_price=trade_data.get('exit_price', 0),
        pnl=pnl,
        pnl_percent=pnl_percent,
        hold_duration=trade_data.get('hold_duration', 'N/A'),
    )


def format_daily_summary(summary_data: dict) -> str:
    """Format daily summary message."""
    total_pnl = summary_data.get('total_pnl', 0)
    
    if total_pnl > 0:
        emoji = "🟢"
        outcome = "PROFIT"
    elif total_pnl < 0:
        emoji = "🔴"
        outcome = "LOSS"
    else:
        emoji = "➖"
        outcome = "BREAKEVEN"
    
    # Format best trade
    best_trade = summary_data.get('best_trade')
    if best_trade:
        best_text = f"{best_trade.get('symbol', 'N/A')} {best_trade.get('action', 'N/A')} ${best_trade.get('pnl', 0):+.2f}"
    else:
        best_text = "N/A"
    
    # Format worst trade
    worst_trade = summary_data.get('worst_trade')
    if worst_trade:
        worst_text = f"{worst_trade.get('symbol', 'N/A')} {worst_trade.get('action', 'N/A')} ${worst_trade.get('pnl', 0):+.2f}"
    else:
        worst_text = "N/A"
    
    # Format agent stats
    agent_stats = summary_data.get('agent_stats', [])
    agent_text = ""
    if agent_stats:
        for agent in sorted(agent_stats, key=lambda x: x.get('pnl', 0), reverse=True)[:3]:
            agent_emoji = "🟢" if agent.get('pnl', 0) > 0 else "🔴" if agent.get('pnl', 0) < 0 else "➖"
            agent_text += f"  {agent_emoji} {agent.get('agent_name', 'Unknown')}: ${agent.get('pnl', 0):+.2f} ({agent.get('trades', 0)} trades)\n"
    else:
        agent_text = "  No agent data available\n"
    
    return DAILY_SUMMARY_TEMPLATE.format(
        emoji=emoji,
        outcome=outcome,
        date=summary_data.get('date', 'Today'),
        total_pnl=total_pnl,
        total_pnl_percent=summary_data.get('total_pnl_percent', 0),
        win_rate=summary_data.get('win_rate', 0),
        wins=summary_data.get('wins', 0),
        losses=summary_data.get('losses', 0),
        breakeven=summary_data.get('breakeven', 0),
        total_trades=summary_data.get('total_trades', 0),
        best_trade_text=best_text,
        worst_trade_text=worst_text,
        agent_stats_text=agent_text,
    )


def format_portfolio_summary(summary_data: dict) -> str:
    """Format portfolio summary message."""
    return PORTFOLIO_SUMMARY_TEMPLATE.format(
        total_value=summary_data.get('total_value', 0),
        cash=summary_data.get('cash', 0),
        market_value=summary_data.get('market_value', 0),
        return_value=summary_data.get('return_value', 0),
        return_pct=summary_data.get('return_pct', 0),
        positions_count=summary_data.get('positions_count', 0),
        paper_or_live='Paper' if summary_data.get('is_paper', True) else 'Live',
    )


def format_positions_list(positions: list) -> str:
    """Format positions list message."""
    positions_text = ""
    for pos in positions[:10]:  # Limit to 10 positions
        pnl = pos.get('unrealized_pnl', 0)
        pnl_pct = pos.get('unrealized_pnl_percent', 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        
        positions_text += f"{emoji} {pos.get('symbol', 'N/A')}\n"
        positions_text += f"  Qty: {pos.get('quantity', 0)} | Price: ${pos.get('current_price', 0):.2f}\n"
        positions_text += f"  PnL: ${pnl:+,.2f} ({pnl_pct:+.1f}%)\n"
        positions_text += "━━━━━━━━━━━━━━━━━━━━\n"
    
    if len(positions) > 10:
        positions_text += f"_...and {len(positions) - 10} more positions_\n"
    
    return POSITIONS_LIST_TEMPLATE.format(
        positions_list=positions_text,
        positions_count=len(positions),
    )


def format_recent_trades(trades: list) -> str:
    """Format recent trades message."""
    trades_text = ""
    for trade in trades[:10]:  # Limit to 10 trades
        pnl = trade.get('pnl', 0) or 0
        pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "➖"
        pnl_text = f"${pnl:+,.2f}" if pnl != 0 else "Open"
        
        trades_text += f"{pnl_emoji} {trade.get('symbol', 'N/A')} {trade.get('side', 'N/A').upper()}\n"
        trades_text += f"  {trade.get('quantity', 0)} @ ${trade.get('price', 0):.2f}\n"
        trades_text += f"  {pnl_text}\n"
        trades_text += "━━━━━━━━━━━━━━━━━━━━\n"
    
    return RECENT_TRADES_TEMPLATE.format(
        trades_list=trades_text,
        total_trades=len(trades),
    )


def format_verification_code(code: str, expires_minutes: int = 10) -> str:
    """Format verification code message."""
    return VERIFICATION_CODE_TEMPLATE.format(
        code=code,
        expires_minutes=expires_minutes,
    )


def format_welcome_message(summary_time: str = "8:00 PM WAT") -> str:
    """Format welcome message."""
    return WELCOME_MESSAGE_TEMPLATE.format(
        summary_time=summary_time,
    )