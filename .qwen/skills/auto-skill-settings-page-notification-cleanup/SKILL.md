---
name: settings-page-notification-cleanup
description: Remove unused notification channels from Settings page, keeping only Telegram for free-tier hosting
source: auto-skill
extracted_at: '2026-06-21T00:00:00.000Z'
---

# Settings Page Notification Cleanup

When simplifying the Settings page to use only Telegram for notifications (driven by free-tier hosting constraints), follow this systematic approach to remove unused notification channels.

## Why

Telegram Bot API is 100% free, requires no QR codes, works on any hosting platform (including Render free tier), and provides better 2-way chat features. Other channels (Discord, Slack, Email/SMTP, SendGrid) add complexity without value for this deployment strategy.

## What to Remove

### 1. TypeScript Interfaces
Remove unused interface definitions:
```typescript
interface DiscordSettings { webhook_url: string; enabled: boolean; configured: boolean; }
interface SlackSettings { webhook_url: string; enabled: boolean; configured: boolean; }
interface EmailSettings { smtp_server: string; smtp_port: number; username: string; password: string; from_email: string; to_emails: string[]; enabled: boolean; configured: boolean; }
```

### 2. State Variables
Remove state declarations for unused services:
```typescript
// REMOVE these:
const [discord, setDiscord] = useState(...)
const [slack, setSlack] = useState(...)
const [email, setEmail] = useState(...)
const [sendgrid, setSendgrid] = useState(...)
const [discordBot, setDiscordBot] = useState(...)
```

### 3. Import Statements
Remove unused component imports:
```typescript
// REMOVE:
import EmailServiceSection from './settings/EmailServiceSection';
import DiscordBotSection from './settings/DiscordBotSection';
```

Remove unused Lucide icons:
```typescript
// FROM:
import { ..., Bell, Mail, Send, DollarSign, Hash, Smartphone, ... } from 'lucide-react';
// TO:
import { ..., DollarSign, ... } from 'lucide-react';
```

### 4. fetchSettings Function
Simplify the notification settings loading to only handle Telegram:

```typescript
// REPLACE this entire block:
if (data.discord_config) { ... }
if (data.slack_config) { ... }
if (data.email_config) { ... }
if (data.telegram_config) { ... } // first block
if (data.telegram_config) { ... } // second block (duplicate)

// WITH:
if (data.telegram_config) {
  setTelegram({
    chat_id: data.telegram_config.chat_id || '',
    bot_token: data.telegram_config.bot_token || '',
    enabled: data.telegram_config.enabled || false,
    chat_enabled: data.telegram_config.chat_enabled || true,
    configured: !!data.telegram_config.chat_id
  });
}
```

### 5. Save Functions
Remove entire save functions:
- `saveDiscord()`
- `saveSlack()`
- `saveEmail()`

### 6. UI Sections
Remove these JSX sections:
- Discord webhook configuration section
- Slack webhook configuration section
- Email SMTP configuration section
- SendGrid email service section
- Discord Bot 2-way chat section

### 7. Update Section Headers
Change the notification section header to reflect Telegram-only approach:

```typescript
// FROM:
<h2>Multi-Channel Notifications</h2>
<p>Receive trade alerts on multiple channels. Configure all channels below.</p>

// TO:
<h2>Telegram Notifications</h2>
<p>Receive trade alerts, daily summaries, and 2-way chat via Telegram.</p>
```

## Verification Checklist

After cleanup, verify:
- [ ] No references to `discord`, `slack`, `email`, `sendgrid`, or `discordBot` variables remain
- [ ] No unused imports in the import statement block
- [ ] TypeScript compiles without errors
- [ ] Only Telegram notification section renders in the UI
- [ ] Settings page loads and saves correctly

## Files Modified

- `frontend/components/SettingsTab.tsx` - Main settings component

## Related Considerations

This cleanup aligns with the free-tier deployment strategy where:
- Render free tier (512MB RAM) cannot run browser-based WhatsApp automation
- Telegram Bot API has no cost and no hosting restrictions
- Single notification channel简化s user configuration and reduces support burden