# Jasper Trades — Simplified UI Wireframes (v2)

**Design goal:** an app a complete beginner can use. **5 screens.** One
primary action: **press START and let the AI trade with practice money.**

No trading jargon in the UI. Every number has a plain-English caption. Guided
tutorials (a 5-minute wizard + one short tour per screen) teach everything.

## Navigation (always visible)

```
MOBILE (bottom bar)                TABLET / DESKTOP (left sidebar)
┌────────────────────────┐         ┌──────────┬──────────────────────┐
│  Home   Trades  Markets │  Settings │  🏠 Home  │                      │
│                         │         │  💼 Trades │                      │
│  [🏠] [💼] [📈] [⚙]     │         │  📈 Markets│      CONTENT        │
└────────────────────────┘         │  ⚙️ Settings│                      │
                                   └──────────┴──────────────────────┘
```

- 5 items. No sub-menus. No hamburger maze.
- Home is the default screen.

---

## Screen 1 — Home

**Purpose: "What is the AI doing right now?" — one glance, one action.**

```
┌─────────────────────────────────────────────────────────────┐
│ 🏠 Home                                             [🔔] [💬] │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  🤖 THE AI TRADER                                       │ │
│ │                                                         │ │
│ │  ● Watching BTC, ETH, EURUSD, AAPL, SOL...              │ │
│ │                                                         │ │
│ │      ┌──────────────────────┐                            │ │
│ │      │  ▶  START            │   ← the ONLY button        │ │
│ │      └──────────────────────┘                            │ │
│ │  "Start with practice money. You can switch to real      │ │
│ │   trading later in Settings."                            │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│  Balance            Today's P&L                              │
│  $10,000.00         +$84.20  (+0.8%)                        │
│  "practice money"   "what I earned today"                    │
│                                                             │
│  ── Recent AI trades ─────────────────────────────────────  │
│  ✅ BUY  BTC     $67,200   · 2m ago                         │
│  ✅ SELL ETH     $3,410    · 1h ago                         │
│  ✅ BUY  SOL     $168      · 3h ago                         │
│  [ See all in Trades → ]                                    │
└─────────────────────────────────────────────────────────────┘
```

Mobile: cards stack vertically. Tablet/desktop: Balance + P&L side by side.

**Notes**
- The status line always explains itself in plain words.
- "Recent AI trades" shows 3; full list lives in **Trades**.
- Old "Agents" screen is gone — a small "AI is thinking…" pulse in the
  status card replaces the old agent dashboard.

---

## Screen 2 — Trades

**Purpose: "What has the AI done for me?"**

```
┌─────────────────────────────────────────────────────────────┐
│ 💼 Trades                                    [PAPER] [LIVE] │
│                                                             │
│  Holdings (what I own)                                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ BTC        0.10      $6,720      +$310  (+4.8%)  🟢   │  │
│  │ SOL        25.0      $4,200      -$45   (-1.1%)  🔴   │  │
│  │ USDC       $1,000    $1,000      $0     (0.0%)  ⚪    │  │
│  └───────────────────────────────────────────────────────┘  │

## Screen 3 — Markets

**Purpose: "What is worth buying today?"**

```
┌─────────────────────────────────────────────────────────────┐
│ 📈 Markets                                     [ 🔍 search ] │
│                                                             │
│  AI Recommendations (plain English)                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 🟢 BUY    Bitcoin   "AI thinks it will go up this     │  │
│  │                     week."              Confidence 72% │  │
│  │ ⚪ HOLD   Ethereum  "AI sees no clear direction."      │  │
│  │ 🔴 SELL   Dogecoin  "AI thinks it will fall."          │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  🔥 Trending right now (crypto + Solana memecoins)          │
│  BONK ▲24%   WIF ▲12%   POPCAT ▲8%   JUP ▲5%               │
│                                                             │
│  [ Advanced research tools (optional) ]  ← small link       │
│   Backtesting · Alpha Zoo · for curious users only          │
└─────────────────────────────────────────────────────────────┘
```

**Notes**
- Recommendations always in **Buy / Hold / Sell** + a one-line reason.
- "Advanced research tools" is a small footer link (not a nav item) so
  beginners never see Backtest/AlphaZoo unless they click it.
- Trending data comes from the Solana memecoin (DexScreener) + CCXT sources.

## Screen 4 — Signals

**Purpose: "What are people saying about my symbols?" — plug in sources, get ranked tips.**

```
┌─────────────────────────────────────────────────────────────┐
│ 📡 Signals                                                 │
│                                                             │
│  My Signal Sources                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ RSS Feed     │  │ Reddit r/... │  │ Telegram @.. │     │
│  │ ✅ Active    │  │ ✅ Active    │  │ 🔌 Connect   │     │
│  │ Last: 2m ago │  │ Last: 8m ago │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│  [+ Add Source]  [Fetch Now]                               │
│                                                             │
│  ── Ranked Tips ─────────────────────────────────────────  │
│  🔵 BTC   LONG   4h    confidence 82%                      │
│     "BTC breaking resistance; watch $68K."                  │
│     ✅ Hit   ❌ Miss                                        │
│                                                             │
│  🔴 ETH   SHORT  1h    confidence 61%                      │
│     "ETH rejected at resistance."                           │
│     ✅ Hit   ❌ Miss                                        │
│                                                             │
│  🔵 SOL   LONG   15m   confidence 74%                      │
│     "Solana memecoin rotation into SOL."                    │
│     ✅ Hit   ❌ Miss                                        │
└─────────────────────────────────────────────────────────────┘
```

**Notes**
- "Add Source" opens a tiny form: pick type (RSS / Reddit / StockTwits / Telegram), paste config (URLs, subreddit, symbols), save.
- **Telegram connect** is a dedicated flow inside Signals: phone → OTP code → 2FA (if enabled) → list joined channels → pick which to track. Session is stored server-side.
- **Fetch Now** scrapes all active sources and asks Gemini to extract tradeable tips (symbol, side, timeframe, confidence).
- Tips are ranked by **confidence** (Gemini score). Tapping Hit/Miss updates the source's hit rate so rankings improve over time.
- No leaderboard of fake traders. This screen shows **your sources ranked by their signal quality**.
- Old `agent_reach` (OpenCLI / rdt-cli / Twitter/Reddit scrapers) removed. Replaced by direct RSS (feedparser), Reddit JSON API, StockTwits API, and Telethon for Telegram.

---

## Screen 5 — Settings

**Purpose: "Make it work for me" — a guided checklist, not a control panel.**

```
┌─────────────────────────────────────────────────────────────┐
│ ⚙️ Settings                          Setup progress: 3 of 5 │
│                                                             │
│  1. 📲 Connect signal sources          [Open Signals]                        │
│     "RSS, Reddit, Telegram channels - ranked by results."                         │
│  2. 💵 Trading mode                                         │
│     [ ● Practice (paper) ]  [ ○ Live (cTrader) ]           │
│     "Practice = play money. Live = real trading."           │
│  3. 👛 Connect a wallet (optional)   🔗 Connect             │
│     "For Solana & crypto on-chain."                         │
│  4. 🤖 AI engine                    ✅ Connected (Gemini)   │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│  Appearance:  Light  Dark                                   │
└─────────────────────────────────────────────────────────────┘
```

**Notes**
- A big friendly **Practice/Live toggle** — not scary broker forms.
- Each row opens a short guided panel with a "❓ How does this work?"
- Advanced items (cTrader OAuth keys, API settings) live behind "Live"
  mode + "Advanced" expander — hidden from beginners.
- Old scattered settings (Binance, Polymarket, dozens of toggles) removed.

---

## Onboarding (updated to match)

### First 5 minutes — one-time wizard (modal, skippable)
1. "Welcome! I'm Jasper — your AI trader. I watch markets for you."
2. "Tap START on Home and I'll trade with practice money — nothing real."
3. "Connect Telegram so I message you every trade I make."
4. "You'll see my trades on the Trades screen, with reasons in plain English."
5. "Done! Ask me anything in the chat bubble, anytime."

### Per-screen tours (short, auto-start once)
- **Home** → points at START button, balance, recent trades.
- **Trades** → points at holdings + the plain-English reasons.
- **Markets** → points at Buy/Hold/Sell cards + trending.
- **Settings** → walks the 5-step checklist.

### Rules
- Beginner-friendly language only ("practice money", never "paper trading").
- Every tour is skippable, one-time, re-launchable from Settings.
- No tutorial mentions features that don't exist in the UI.

---

## What was removed (and where it went)

| Old screen | New home |
|---|---|
| Agents | Folded into Home status card ("AI is watching…") |
| Portfolio | Folded into Home + Trades |
| CopyTrade | Replaced by Signals screen |
| Backtest | Hidden footer link on Markets ("Advanced research tools") |
| AlphaZoo | Hidden footer link on Markets |
| agent_reach | Removed; replaced by signal_sources (RSS/Reddit/StockTwits/Telegram) |
| Polymarket / Binance / dozens of settings | Removed entirely |
