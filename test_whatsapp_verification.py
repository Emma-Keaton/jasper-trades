"""
WhatsApp Verification Test Script
Tests the WhatsApp verification endpoint and displays the verification code.

Usage:
    python test_whatsapp_verification.py
"""
import requests
import json

API_URL = "http://localhost:8000"
DEVICE_ID = "test-device-" + str(int(__import__('time').time()))

def test_whatsapp_verification():
    """Test WhatsApp verification endpoint"""
    print("=" * 60)
    print("  WhatsApp Verification Test")
    print("=" * 60)
    print()
    
    # Get phone number from user
    phone = input("Enter your WhatsApp number (with country code): ").strip()
    if not phone:
        phone = "+2348123456789"  # Default test number
    
    print(f"\nRequesting verification code for: {phone}")
    print("-" * 60)
    
    # Request verification code
    try:
        response = requests.post(
            f"{API_URL}/api/v1/settings/whatsapp/verify/request",
            headers={
                "Content-Type": "application/json",
                "X-Device-ID": DEVICE_ID,
            },
            json={"phone_number": phone},
            timeout=10
        )
        
        result = response.json()
        
        print("\nResponse:")
        print(json.dumps(result, indent=2))
        print("-" * 60)
        
        if response.status_code == 200:
            print("\n✅ SUCCESS!")
            
            # Check if we have the code
            if "_debug_code" in result:
                code = result["_debug_code"]
                print(f"\n{'='*60}")
                print(f"  YOUR VERIFICATION CODE: {code}")
                print(f"{'='*60}")
                print(f"\nThis code was logged to the backend console.")
                print(f"Enter this code in the frontend to verify your number.")
                print(f"\nNote: In production, this code would be sent via WhatsApp.")
                print(f"Currently, OpenWA session may not be active.")
            else:
                print("\nCheck your WhatsApp for the verification code!")
            
            print(f"\nDevice ID: {DEVICE_ID}")
            print(f"Code expires in: {result.get('expires_in_minutes', 10)} minutes")
            
            return result
        else:
            print(f"\n❌ FAILED: {result.get('detail', 'Unknown error')}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to backend server")
        print(f"Make sure the backend is running at {API_URL}")
        print("\nTo start the backend:")
        print("  cd backend")
        print("  python -m uvicorn app.main:app --reload")
        return None
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return None

if __name__ == "__main__":
    result = test_whatsapp_verification()
    
    if result:
        print("\n" + "=" * 60)
        print("Test complete!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Test failed!")
        print("=" * 60)