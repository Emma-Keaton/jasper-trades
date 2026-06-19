# WhatsApp Notifications - Setup & Troubleshooting Guide

## 🚀 Quick Setup

### For Local Development

1. **Install Dependencies**
   ```bash
   cd backend
   npm install @open-wa/wa-automate --legacy-peer-deps
   ```

2. **Start Backend**
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

3. **Test Verification**
   ```bash
   python test_whatsapp_verification.py
   ```
   This will display the verification code in the console.

### For Render Deployment

**No additional setup needed!** The Dockerfile already includes:
- Node.js installation
- OpenWA installation (`@open-wa/wa-automate`)
- Proper configuration

WhatsApp will work automatically after deployment to Render.

---

## 🔧 Troubleshooting

### Issue: "Failed to send verification code"

**Symptom:** Error when clicking "Send Code" in Settings

**Cause:** OpenWA server not running or WhatsApp session not activated

**Solution:**

1. **Check if OpenWA is running:**
   ```
   curl http://localhost:3001/health
   ```
   
   Expected response:
   ```json
   {
     "status": "ok",
     "sessionActive": true
   }
   ```

2. **Check backend logs for:**
   ```
   [info] Embedded OpenWA started on port 3001
   ```

3. **If OpenWA not started:**
   - Verify Node.js is installed: `node --version`
   - Reinstall OpenWA: `npm install @open-wa/wa-automate --legacy-peer-deps`
   - Restart backend

4. **For Development - Use Console Code:**
   - Backend logs show: `🔐 VERIFICATION CODE GENERATED: 123456`
   - Use this code for testing without WhatsApp

---

## 📱 WhatsApp Session Activation

OpenWA requires scanning a QR code with your WhatsApp phone:

### Development Mode (Current)
- Verification code is logged to backend console
- Use the code from logs to verify
- No QR code needed for testing

### Production Mode (With OpenWA Running)
1. Backend starts → OpenWA starts automatically
2. Check logs for QR code URL
3. Open QR scanner in browser
4. Scan with WhatsApp → Settings → Linked Devices
5. Session activates → Verification codes sent via WhatsApp

---

## 🐛 Common Issues & Fixes

### 1. "Module not found: @open-wa/wa-automate"

**Fix:**
```bash
cd backend
npm install @open-wa/wa-automate --legacy-peer-deps
```

### 2. "Port 3001 already in use"

**Fix:**
```bash
# Windows
netstat -ano | findstr :3001
taskkill /F /PID <PID>

# Or change OpenWA port
# In backend, set env: OPENWA_PORT=3002
```

### 3. "OpenWA failed to start: Cannot find module './utils'"

**Fix:** Corrupted axios installation
```bash
cd backend
rmdir /s /q node_modules\@open-wa\wa-decrypt\node_modules\axios
npm install axios
```

### 4. QR code not appearing

**Fix:** Use development mode
- Verification code is logged to console
- No QR code needed for local dev

---

## 📊 Render Deployment

### What Happens on Render:

1. **Build Phase (render-build.sh):**
   ```bash
   npm install @open-wa/wa-automate
   mkdir -p backend/data/openwa-session
   ```

2. **Startup Phase:**
   - Backend starts
   - OpenWA starts automatically on port 3001
   - WhatsApp session initializes

3. **Runtime:**
   - Users request verification codes
   - Codes sent via WhatsApp (not console)
   - Daily summaries sent at 8 PM WAT

### Expected Logs:
```
💬 Installing OpenWA for WhatsApp...
✅ OpenWA installed
[info] Embedded OpenWA started on port 3001
[info] Application startup complete
```

---

## 🧪 Testing Verification Flow

### Step 1: Request Code
```bash
curl -X POST "http://localhost:8000/api/v1/settings/whatsapp/verify/request" \
  -H "Content-Type: application/json" \
  -H "X-Device-ID: test123" \
  -d '{"phone_number": "+2348123456789"}'
```

### Step 2: Get Code from Console
Look for:
```
🔐 VERIFICATION CODE GENERATED: 123456 for +2348123456789
```

### Step 3: Confirm Verification
```bash
curl -X POST "http://localhost:8000/api/v1/settings/whatsapp/verify/confirm" \
  -H "Content-Type: application/json" \
  -H "X-Device-ID: test123" \
  -d '{"phone_number": "+2348123456789", "verification_code": "123456"}'
```

Expected response:
```json
{
  "success": true,
  "message": "WhatsApp number verified successfully"
}
```

---

## 📝 Development vs Production

| Feature | Development | Production (Render) |
|---------|-------------|---------------------|
| Verification Code | Logged to console | Sent via WhatsApp |
| OpenWA Session | Optional | Required |
| QR Code Scan | Not needed | Required |
| Daily Summaries | Logged | Sent via WhatsApp |
| Session Persistence | Local file | Render disk (ephemeral) |

---

## 🔒 Security Notes

- Verification codes: 6 digits, expire in 10 minutes
- Phone numbers stored encrypted in database
- WhatsApp session tokens stored securely
- Production: Re-verify after app restart (ephemeral filesystem)

---

## 📞 Support

If issues persist:

1. **Check backend logs:**
   ```bash
   # Look for WhatsApp-related errors
   grep -i "whatsapp\|openwa" backend/logs/*.log
   ```

2. **Test with script:**
   ```bash
   python test_whatsapp_verification.py
   ```

3. **Verify dependencies:**
   ```bash
   cd backend
   npm ls @open-wa/wa-automate
   ```

4. **Restart everything:**
   ```bash
   # Stop all
   taskkill /F /IM python.exe
   taskkill /F /IM node.exe
   
   # Start backend
   cd backend
   python -m uvicorn app.main:app --reload
   ```

---

**Last Updated:** June 19, 2026
**Version:** 1.0.0