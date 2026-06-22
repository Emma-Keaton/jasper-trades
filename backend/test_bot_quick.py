"""Quick Telegram bot test"""
import asyncio
import httpx

BOT_TOKEN = "8877066314:AAEk7sBrIK4ASwulAXAMr0iNltnEI1XzmWY"
# Try different chat ID formats
CHAT_IDS = [2021169192, -2021169192, "2021169192", "-2021169192"]

async def test():
    bot_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test 1: Get bot info
        print("Testing bot info...")
        response = await client.get(f"{bot_url}/getMe")
        if response.status_code == 200:
            data = response.json()
            bot = data["result"]
            print(f"✅ Bot: @{bot['username']}")
        else:
            print(f"❌ Failed: {response.text}")
            return
        
        # Test 2: Send message
        print("Sending test message...")
        for chat_id in CHAT_IDS:
            response = await client.post(
                f"{bot_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": f"🔊 *Jasper Trades Test*\n\n✅ Success with chat ID: `{chat_id}`\n\nCheck your Telegram!",
                    "parse_mode": "Markdown"
                }
            )
            
            if response.status_code == 200:
                print(f"✅ Message sent with chat ID: {chat_id}")
                print(f"   Check your Telegram - you should receive the message.")
                return
        
        print(f"❌ Failed with all chat ID formats. Make sure you:")
        print(f"   1. Started a chat with @{bot['username']}")
        print(f"   2. Clicked the START button")
        print(f"   3. Sent /start message")

asyncio.run(test())