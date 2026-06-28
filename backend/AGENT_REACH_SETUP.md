# Agent Reach Configuration Guide

## Current Status ✅

**Installed & Ready:**
- ✅ Agent Reach CLI installed
- ✅ Twitter CLI installed
- ✅ browser-cookie3 installed
- ✅ V2EX working (live news fetching)
- ✅ RSS ready
- ✅ Jina Reader ready

## To Enable Twitter & Reddit

1. **Log in to Chrome:**
   - Open Chrome
   - Log in to https://twitter.com (or https://x.com)
   - Log in to https://reddit.com
   - Keep Chrome open

2. **Run Configuration:**
   ```bash
   cd backend
   configure-agent-reach.bat
   ```

   Or manually:
   ```bash
   agent-reach configure --from-browser chrome twitter-cookies
   agent-reach configure --from-browser chrome reddit-cookies
   ```

3. **Verify:**
   ```bash
   agent-reach doctor
   ```
   
   You should see:
   - ✅ Twitter 推文 and search
   - ✅ Reddit 帖子和评论

## What This Does

- Extracts browser cookies from Chrome
- Saves to `C:\Users\USER\.agent-reach\config.yaml`
- Enables real-time Twitter/Reddit news fetching
- Works automatically for your AI trading agents

## After Configuration

Your agents will automatically get:
- Real-time Twitter financial news
- Reddit r/wallstreetbets sentiment
- Multi-source consensus detection
- Enhanced trading signals

## For Render Deployment

On Render, you have 2 options:

**Option 1: Use only public channels (no config needed)**
- V2EX: Works immediately
- RSS: Add your feeds in `.env`
- Jina Reader: Works immediately

**Option 2: Configure locally, then deploy config**
- Configure Twitter/Reddit locally
- Upload `~/.agent-reach/config.yaml` to Render
- Or just use public channels

## Troubleshooting

**"No cookies found"**
- Make sure you're logged in to the sites in Chrome
- Close Chrome and try again
- Chrome must be the default browser

**"Unable to get key for cookie decryption"**
- Close Chrome completely
- Try running as Administrator
- browser-cookie3 may need permission to access Chrome data

**"twitter-cli not found"**
- Install: `pip install agent-reach`
- Verify: `twitter --help`