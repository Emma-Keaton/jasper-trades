#!/usr/bin/env python3
"""
Telegram Bot Quick Setup Script
Tests bot configuration and sends a test message
"""
import asyncio
import httpx
import sys

# Configuration
BOT_TOKEN = input("Enter your Telegram Bot Token: ").strip()
CHAT_ID = input("Enter your Telegram Chat ID: ").strip()


async def test_bot():
    """Test Telegram bot connection"""
    print("\n🔍 Testing Telegram Bot Connection...\n")
    
    bot_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    
    try:
        # Test 1: Get bot info
        print("1. Checking bot info...")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{bot_url}/getMe")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    bot = data["result"]
                    print(f"   ✅ Bot found: @{bot.get('username', 'unknown')}")
                    print(f"   Bot Name: {bot.get('first_name', 'unknown')}")
                    print(f"   Bot ID: {bot.get('id', 'unknown')}")
                else:
                    print(f"   ❌ Invalid bot token")
                    return False
            else:
                print(f"   ❌ Failed to connect: {response.status_code}")
                return False
        
        # Test 2: Send test message
        print("\n2. Sending test message...")
        test_message = (
            "🔊 *Jasper Trades Test*\n\n"
            "✅ Telegram bot is working!\n\n"
            "You will now receive:\n"
            "• Trade executions\n"
            "• Trade closures (with PnL)\n"
            "• Daily summaries\n"
            "• System alerts\n\n"
            "🤖 Jasper Trades AI"
        )
        
        response = await client.post(
            f"{bot_url}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": test_message,
                "parse_mode": "Markdown"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                print(f"   ✅ Test message sent successfully!")
                print(f"   Check your Telegram chat")
            else:
                print(f"   ❌ Failed to send message: {data.get('description')}")
                return False
        else:
            print(f"   ❌ API error: {response.status_code}")
            return False
        
        print("\n✅ All tests passed! Telegram bot is configured correctly.\n")
        return True
        
    except httpx.ConnectError as e:
        print(f"   ❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("JASPER TRADES - TELEGRAM BOT QUICK TEST")
    print("=" * 60)
    print("\nGet your bot token from @BotFather on Telegram")
    print("Get your chat ID by messaging @userinfobot on Telegram\n")
    
    success = asyncio.run(test_bot())
    
    if success:
        print("Next steps:")
        print("1. Add TELEGRAM_BOT_TOKEN to your .env file")
        print("2. Restart the backend: python -m uvicorn app.main:app --reload")
        print("3. Message your bot on Telegram: t.me/<your_bot_username>")
        print("4. Use /verify to get your chat ID")
        print("5. Add chat ID in Jasper Trades app Settings → Telegram\n")
        sys.exit(0)
    else:
        print("\n❌ Setup failed. Please check your bot token and chat ID.\n")
        sys.exit(1)