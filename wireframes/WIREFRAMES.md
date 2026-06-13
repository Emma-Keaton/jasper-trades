# Jasper Trades - UI Wireframes

This document contains detailed wireframes for all screens in the Jasper Trades application. Use these specifications to build high-fidelity prototypes.

---

## Table of Contents

1. [Layout & Navigation](#1-layout--navigation)
2. [Dashboard](#2-dashboard)
3. [Agents Management](#3-agents-management)
4. [Signals Feed](#4-signals-feed)
5. [Copy Trading](#5-copy-trading)
6. [Backtest Interface](#6-backtest-interface)
7. [Alpha Zoo Browser](#7-alpha-zoo-browser)
8. [Portfolio](#8-portfolio)
9. [Settings](#9-settings)
   - [9.1 API Keys](#91-api-keys)
   - [9.2 Trading Caps & Risk Limits](#92-trading-caps--risk-limits)
   - [9.3 Market Data Providers](#93-market-data-providers)
   - [9.4 Email Service (SendGrid)](#94-email-service-sendgrid)
   - [9.5 Discord Bot](#95-discord-bot)
   - [9.6 LLM Model Configuration](#96-llm-model-configuration)
   - [9.7 Notifications](#97-notifications)
   - [9.8 Data & Storage](#98-data--storage)

---

## Design System

### Colors
```
Primary:        #3B82F6 (Blue-500)
Primary Dark:   #2563EB (Blue-600)
Secondary:      #10B981 (Emerald-500)
Danger:         #EF4444 (Red-500)
Warning:        #F59E0B (Amber-500)
Info:           #6366F1 (Indigo-500)

Background:     #0F172A (Slate-900)
Surface:        #1E293B (Slate-800)
Surface Light:  #334155 (Slate-700)

Text Primary:   #F8FAFC (Slate-50)
Text Secondary: #94A3B8 (Slate-400)
Border:         #475569 (Slate-600)
```

### Typography
```
Headings: Inter, sans-serif
Body:     Inter, sans-serif
Mono:     JetBrains Mono, monospace (for numbers, code)
```

### Spacing
```
xs:  4px
sm:  8px
md:  16px
lg:  24px
xl:  32px
2xl: 48px
```

### Border Radius
```
sm:   4px
md:   8px
lg:   12px
xl:   16px
full: 9999px
```

---

## 1. Layout & Navigation

### Shell Layout (All Pages)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ HEADER (Height: 64px)                                                          │
│ ┌────────────────────┬──────────────────────────────────┬───────────────────┐ │
│ │ LOGO + NAME        │ GLOBAL SEARCH                    │ USER + NOTIF      │ │
│ │ [Jasper] Trades    │ [🔍 Search commands, symbols...] │ [🔔] [Avatar ▼]   │ │
│ │                    │                                  │                   │ │
│ └────────────────────┴──────────────────────────────────┴───────────────────┘ │
├─────────┬──────────────────────────────────────────────────────────────────────┤
│ SIDEBAR │ MAIN CONTENT AREA                                                    │
│ (64px   │                                                                      │
│  collapsed,                                                                    │
│  240px   │                                                                      │
│  expanded)                                                                     │
│ │        │                                                                      │
│ │ [📊]   │                                                                      │
│ │ Dashboard                                                                  │ │
│ │                                                                            │ │
│ │ [🤖]   │                                                                      │
│ │ Agents                                                                     │ │
│ │                                                                            │ │
│ │ [📡]   │                                                                      │
│ │ Signals                                                                    │ │
│ │                                                                            │ │
│ │ [👥]   │                                                                      │
│ │ Copy Trade                                                                 │ │
│ │                                                                            │ │
│ │ [📈]   │                                                                      │
│ │ Backtest                                                                   │ │
│ │                                                                            │ │
│ │ [🔮]   │                                                                      │
│ │ Alpha Zoo                                                                  │ │
│ │                                                                            │ │
│ │ [💼]   │                                                                      │
│ │ Portfolio                                                                  │ │
│ │                                                                            │ │
│ │ [⚙️]   │                                                                      │
│ │ Settings                                                                   │ │
│ │                                                                            │ │
│ └──────────────────────────────────────────────────────────────────────────────┘
│ STATUS BAR (Height: 32px)                                                        │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ [●] System: Online  │  Agents: 4 Active  │  Portfolio: $102,450 (+2.4%)  │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### Header
```yaml
Position: Fixed top, z-index: 1000
Height: 64px
Background: Surface (#1E293B)
Border-bottom: 1px solid Border (#475569)

Logo Section:
  - Icon: 32x32px, 8px margin-left
  - Text: "Jasper Trades", 20px bold, Inter

Search Section:
  - Width: 400px (expandable to 600px on focus)
  - Height: 40px
  - Placeholder: "Search commands, symbols, agents..."
  - Shortcut badge: "⌘K" (right aligned)

User Section:
  - Notification bell: 24x24px icon, badge counter
  - Avatar: 32x32px circle, dropdown menu
```

#### Sidebar
```yaml
Position: Fixed left, z-index: 900
Width: 64px (collapsed), 240px (expanded)
Background: Surface (#1E293B)
Border-right: 1px solid Border (#475569)

Navigation Items:
  - Height: 48px each
  - Icon: 20x20px
  - Text: 14px, appears when expanded
  - Hover: Surface Light (#334155)
  - Active: Primary (#3B82F6) background 10% opacity
  - Transition: 200ms ease

Collapse Toggle:
  - Position: Bottom of sidebar
  - Icon: Chevron left/right
  - Height: 40px
```

#### Status Bar
```yaml
Position: Fixed bottom
Height: 32px
Background: Background (#0F172A)
Border-top: 1px solid Border (#475569)
Font-size: 12px
Text-color: Text Secondary (#94A3B8)

Sections (left to right):
  - System status: Dot indicator + text
  - Agent status: Count of active agents
  - Portfolio summary: Current value + 24h change
```

---

## 2. Dashboard

### Purpose
Main trading dashboard showing real-time overview of agents, portfolio, and market activity.

### Layout

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ DASHBOARD                                                       [Auto-refresh: ON] │
├────────────────────────────────────────────────────────────────────────────────┤
│ PORTFOLIO SUMMARY (Height: 200px)                                              │
│ ┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐     │
│ │ Total Value     │ 24h P&L         │ Today's Trades  │ Active Agents   │     │
│ │                 │                 │                 │                 │     │
│ │ $102,450.00     │ +$2,450.00      │ 12              │ 4 / 4           │     │
│ │                 │ (+2.45%)        │                 │                 │     │
│ │                 │ [📈 Green]      │ [↗️]            │ [🟢 All active] │     │
│ └─────────────────┴─────────────────┴─────────────────┴─────────────────┘     │
├────────────────────────────────────────────────────────────────────────────────┤
│ AGENT ACTIVITY (Height: 400px)                                                 │
│ ┌──────────────────────────────────────────────────────────────────────────┐   │
│ │ [Real-time Feed]                                    [Clear] [Settings▼] │   │
│ ├──────────────────────────────────────────────────────────────────────────┤   │
│ │ [10:42:33] [🤖 Director]                                                 │   │
│ │ Analyzed market sentiment: BULLISH on tech sector                       │   │
│ │ Triggered by: NVDA earnings beat, +8% after hours                       │   │
│ │                                                                          │   │
│ │ [10:42:35] [📊 Quant]                                                    │   │
│ │ Signal generated: BUY NVDA @ $890                                        │   │
│ │ Confidence: 87%, Expected upside: +12%                                   │   │
│ │                                                                          │   │
│ │ [10:42:38] [🛡️ Risk]                                                      │   │
│ │ Risk check passed: Position size $5,000 (5% of portfolio)               │   │
│ │ Max loss: -$750 (-0.73% portfolio)                                       │   │
│ │                                                                          │   │
│ │ [10:42:40] [⚡ Execution]                                                 │   │
│ │ Order executed: BUY 5.6 shares NVDA @ $889.50                           │   │
│ │ Broker:  Paper | Status: FILLED                                    │   │
│ │                                                                          │   │
│ └──────────────────────────────────────────────────────────────────────────┘   │
├────────────────────────────────────────────────────────────────────────────────┤
│ POSITION CHART (Height: 300px)                                                 │
│ ┌──────────────────────────────────────────────────────────────────────────┐   │
│ │ [Equity Curve]        [1D] [1W] [1M] [3M] [YTD] [ALL]                   │   │
│ │                                                                          │   │
│ │    $105K ┤                                               ╭──╮            │   │
│ │          │                                          ╭───╯  ╰╮           │   │
│ │    $100K ┤                 ╭─────────────────────────╯     ╰──╮         │   │
│ │          │            ╭────╯                                  ╰╮        │   │
│ │     $95K ┤───────╮────╯                                       ╰──╮     │   │
│ │          │       │                                              │      │   │
│ │     $90K ┴───────┴──────────────────────────────────────────────┴────  │   │
│ │          Jan 1   Jan 15   Feb 1   Feb 15   Mar 1   Mar 15   Apr 1      │   │
│ │                                                                          │   │
│ │ Current: $102,450  |  High: $105,200  |  Low: $89,500                    │   │
│ └──────────────────────────────────────────────────────────────────────────┘   │
├────────────────────────────────────────────────────────────────────────────────┤
│ TOP HOLDINGS (Height: 250px)                                                   │
│ ┌──────────────────────────────────────────────────────────────────────────┐   │
│ │ Symbol │ Name              │ Shares │ Price    │ Value     │ P&L       │   │
│ ├────────┼───────────────────┼────────┼──────────┼───────────┼───────────┤   │
│ │ NVDA   │ NVIDIA Corp       │ 5.6    │ $890.00  │ $4,984    │ +$450 +9% │   │
│ │ AAPL   │ Apple Inc         │ 12.0   │ $175.50  │ $2,106    │ +$120 +6% │   │
│ │ MSFT   │ Microsoft Corp    │ 8.5    │ $420.00  │ $3,570    │ +$280 +8% │   │
│ │ BTC    │ Bitcoin           │ 0.45   │ $68,500  │ $30,825   │ +$2,100   │   │
│ │ ETH    │ Ethereum          │ 2.1    │ $3,450   │ $7,245    │ +$450     │   │
│ └──────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### Portfolio Summary Cards
```yaml
Grid: 4 columns (responsive: 2 on tablet, 1 on mobile)
Card padding: 16px
Background: Surface (#1E293B)
Border-radius: lg (12px)
Border: 1px solid Border (#475569)

Value:
  - Font: 28px bold, JetBrains Mono
  - Color: Text Primary (#F8FAFC)

Change:
  - Positive: Secondary (#10B981)
  - Negative: Danger (#EF4444)
  - Font: 14px with percentage in parentheses

Icon/Indicator: Right side of each card
```

#### Agent Activity Feed
```yaml
Container:
  - Height: 400px
  - Overflow-y: auto
  - Background: Surface (#1E293B)
  - Border-radius: lg (12px)
  - Padding: 16px

Feed Item:
  - Padding: 12px vertical
  - Border-bottom: 1px solid Border (#475569)
  - Gap: 8px between elements

Timestamp:
  - Font: 12px monospace
  - Color: Text Secondary (#94A3B8)

Agent Badge:
  - Background: Primary (#3B82F6) 20% opacity
  - Text: 12px bold
  - Padding: 4px 8px
  - Border-radius: md (8px)

Message:
  - Font: 14px
  - Color: Text Primary (#F8FAFC)

Metadata (triggered by, confidence, etc.):
  - Font: 13px
  - Color: Text Secondary (#94A3B8)
  - Margin-top: 4px
```

#### Equity Chart
```yaml
Container:
  - Background: Surface (#1E293B)
  - Border-radius: lg (12px)
  - Padding: 16px

Timeframe Selector:
  - Position: Top right
  - Buttons: 1D, 1W, 1M, 3M, YTD, ALL
  - Active: Primary background
  - Inactive: Transparent

Chart:
  - Type: Area chart with gradient
  - Line color: Primary (#3B82F6)
  - Fill: Primary with 20% opacity gradient
  - Grid lines: Border color (#475569)
  - X-axis labels: Dates, 14px
  - Y-axis labels: Currency, 14px

Stats Bar:
  - Position: Bottom
  - Font: 13px
  - Gap: 24px between stats
```

#### Top Holdings Table
```yaml
Container:
  - Background: Surface (#1E293B)
  - Border-radius: lg (12px)
  - Padding: 16px

Table Header:
  - Font: 12px bold, uppercase
  - Color: Text Secondary (#94A3B8)
  - Border-bottom: 2px solid Border

Table Row:
  - Height: 48px
  - Border-bottom: 1px solid Border (#475569)
  - Hover: Surface Light (#334155)

Columns:
  - Symbol: 80px, bold, Primary color
  - Name: 160px
  - Shares: 80px, right-aligned, monospace
  - Price: 100px, right-aligned, monospace
  - Value: 100px, right-aligned, monospace
  - P&L: 120px, right-aligned, color-coded

P&L Coloring:
  - Positive: Secondary (#10B981)
  - Negative: Danger (#EF4444)
```

---

## 3. Agents Management

### Purpose
View, configure, and control all trading agents.

### Layout

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ AGENTS MANAGEMENT                                               [+ New Custom Agent] │
├────────────────────────────────────────────────────────────────────────────────┤
│ AGENT STATUS OVERVIEW (Height: 120px)                                          │
│ ┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐       │
│ │ Director    │ Quant       │ Risk        │ Execution   │ Custom      │       │
│ │ [🟢 Running]│ [🟢 Running]│ [🟢 Running]│ [🟢 Running]│ [⚪ Stopped]│       │
│ │ 45ms avg    │ 120ms avg   │ 85ms avg    │ 55ms avg    │ -           │       │
│ │ [Stop] [►]  │ [Stop] [⚙️] │ [Stop] [⚙️] │ [Stop] [⚙️] │ [Start] [⚙️]│       │
│ └─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘       │
├────────────────────────────────────────────────────────────────────────────────┤
│ AGENT DETAILS (Tabbed Interface)                                               │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ [Director▼]  [Performance]  [Configuration]  [Logs]  [Skills]             │ │
│ ├────────────────────────────────────────────────────────────────────────────┤ │
│ │                                                                           │ │
│ │ AGENT: DIRECTOR                                                           │ │
│ │ ───────────────────────────────────────────────────────────────────────── │ │
│ │                                                                           │ │
│ │ Left Column (400px)                      Right Column (Remaining)         │ │
│ │ ┌─────────────────────────────┐          ┌─────────────────────────────┐  │ │
│ │ │ Status: 🟢 Running          │          │ CURRENT ACTIVITY            │  │ │
│ │ │ Uptime: 2h 15m 42s          │          │ ─────────────────────────   │  │ │
│ │ │ Last Action: 2s ago         │          │                             │  │ │
│ │ │                             │          │ Scanning market news...     │  │ │
│ │ │ STATISTICS                  │          │                             │  │ │
│ │ │ ─────────                   │          │ [█████████░] 85% complete   │  │ │
│ │ │ Total Decisions: 247        │          │                             │  │ │
│ │ │ Avg Response: 45ms          │          │ Estimated: 3s remaining     │  │ │
│ │ │ Success Rate: 94.3%         │          │                             │  │ │
│ │ │                             │          │ ─────────────────────────── │  │ │
│ │ │ RECENT SIGNALS              │          │                             │  │ │
│ │ │ ──────────────              │          │ LAST 5 DECISIONS            │  │ │
│ │ │ [NVDA BUY ↗] [AAPL HOLD →]  │          │ ─────────────────────────   │  │ │
│ │ │ [MSFT SELL ↘] [TSLA BUY ↗]  │          │ 10:42 - NVDA BUY (87% conf) │  │ │
│ │ │ [BTC HOLD →]  [ETH BUY ↗]   │          │ 10:38 - AAPL HOLD (62% conf)│  │ │
│ │ │                             │          │ 10:35 - MSFT SELL (71% conf)│  │ │
│ │ │ QUICK ACTIONS               │          │ 10:30 - TSLA BUY (92% conf) │  │ │
│ │ │ ────────────                │          │ 10:25 - BTC HOLD (55% conf) │  │ │
│ │ │ [Refresh] [Pause] [Reset]   │          │                             │  │ │
│ │ └─────────────────────────────┘          └─────────────────────────────┘  │ │
│ │                                                                           │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────┤
│ LLM CONFIGURATION                                                              │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ Model Selection: [meta/llama-3.3-70b-instruct     ▼]                       │ │
│ │                 ───────────────────────────────────────────────────────    │ │
│ │ Speed: ●●●○○  |  Accuracy: ●●●●○  |  Cost: ●●●○○                         │ │
│ │                                                                           │ │
│ │ Temperature: [0.7━━━━━━○━━━━] 0.7                                        │ │
│ │ Max Tokens:  [━━━━━━━━━━○━━━] 1024                                       │ │
│ │ Timeout:     [━━━━○━━━━━━━━━━] 5000ms                                    │ │
│ │                                                                           │ │
│ │ [Test Connection]  [Save Configuration]                                    │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### Agent Status Cards
```yaml
Grid: 5 columns (responsive: 3 on tablet, 2 on mobile)
Card width: 200px
Padding: 16px
Background: Surface (#1E293B)
Border-radius: lg (12px)
Border: 1px solid Border

Status Indicator:
  - Running: Green dot (#10B981) + "Running" text
  - Stopped: Gray dot (#64748B) + "Stopped" text
  - Error: Red dot (#EF4444) + "Error" text
  - Loading: Pulsing yellow dot

Response Time:
  - Font: 14px monospace
  - Color: Text Secondary

Action Buttons:
  - Stop/Start: Primary button
  - Settings: Icon button (gear)
  - Size: 32x32px
```

#### Agent Details Tabs
```yaml
Tab Bar:
  - Background: Surface Light (#334155)
  - Padding: 8px 16px
  - Gap: 4px between tabs

Tab:
  - Padding: 8px 16px
  - Border-radius: md (8px) top corners
  - Active: Background Primary, text white
  - Inactive: Transparent, text Secondary
  - Hover: Surface Light

Tab Content:
  - Padding: 24px
  - Background: Surface
```

#### Performance Tab
```yaml
Layout: 2-column grid (400px | remaining)

Statistics Panel:
  - Background: Surface Light
  - Padding: 16px
  - Border-radius: lg
  - Margin-bottom: 16px

Stat Item:
  - Label: 13px, Text Secondary
  - Value: 16px bold, Text Primary
  - Gap: 4px

Progress Bar (for current activity):
  - Height: 8px
  - Background: Border color
  - Fill: Primary gradient
  - Border-radius: full
```

#### Configuration Tab
```yaml
Model Selector:
  - Width: 100%
  - Height: 40px
  - Background: Background (#0F172A)
  - Border: 1px solid Border
  - Border-radius: md
  - Padding: 8px 12px

Model Info Bar:
  - Display: Flex, gap 24px
  - Items: Speed, Accuracy, Cost
  - Dots: 5 circles, filled based on rating

Slider:
  - Track height: 4px
  - Thumb: 16px circle, Primary color
  - Display current value on right

Test Button:
  - Style: Secondary (outlined)
Save Button:
  - Style: Primary (filled)
```

---

## 4. Signals Feed

### Purpose
Real-time feed of all trading signals from AI agents and external sources.

### Layout

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ SIGNALS FEED                                                    [Filters ▼] [Subscribe] │
├────────────────────────────────────────────────────────────────────────────────┤
│ FILTER BAR                                                                     │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ Agent:  [All Agents     ▼]  Asset: [All Assets  ▼]  Type: [All Types  ▼] │ │
│ │ Confidence: [●●●●○] 4+ stars    Time: [Last 24 hours ▼]                   │ │
│ │ [Applied: Director ●] [NVDA ●] [BUY ●]                        [Clear All] │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────┤
│ SIGNALS LIST                                                                   │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ [🔴 LIVE] 32 signals received today                                     │ │
│ ├────────────────────────────────────────────────────────────────────────────┤ │
│ │ ┌────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ [BUY] NVDA - NVIDIA Corporation                                      │ │ │
│ │ │ ────────────────────────────────────────────────────────────────────   │ │ │
│ │ │ Agent: Director | Confidence: ████████░░ 87% | Generated: 2m ago      │ │ │
│ │ │                                                                        │ │ │
│ │ │ Thesis: Strong Q4 earnings beat, data center revenue +427% YoY. AI    │ │ │
│ │ │ demand accelerating. Price target raised to $1,050.                   │ │ │
│ │ │                                                                        │ │ │
│ │ │ Suggested Action: BUY 5-7 shares (~$4,500-6,200)                      │ │ │
│ │ │ Target Price: $1,050 (+18% upside)                                    │ │ │
│ │ │ Stop Loss: $800 (-10% downside)                                       │ │ │
│ │ │                                                                        │ │ │
│ │ │ [Execute Trade] [Add to Watchlist] [Share] [Dismiss]                  │ │ │
│ │ └────────────────────────────────────────────────────────────────────────┘ │ │
│ │                                                                            │ │
│ │ ┌────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ [HOLD] AAPL - Apple Inc                                                │ │ │
│ │ │ ────────────────────────────────────────────────────────────────────   │ │ │
│ │ │ Agent: Quant | Confidence: ██████░░░░ 62% | Generated: 15m ago        │ │ │
│ │ │                                                                        │ │ │
│ │ │ Thesis: Mixed signals. iPhone sales strong in China but services     │ │ │
│ │ │ growth slowing. Waiting for clearer directional indicator.            │ │ │
│ │ │                                                                        │ │ │
│ │ │ Current Position: 12 shares | Avg Cost: $165.50 | P&L: +$120 (+6%)   │ │ │
│ │ │                                                                        │ │ │
│ │ │ [Execute Trade] [Add to Watchlist] [Share] [Dismiss]                  │ │ │
│ │ └────────────────────────────────────────────────────────────────────────┘ │ │
│ │                                                                            │ │
│ │ ┌────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ [SELL] TSLA - Tesla Inc                                                │ │ │
│ │ │ ────────────────────────────────────────────────────────────────────   │ │ │
│ │ │ Agent: Risk | Confidence: ███████░░░ 71% | Generated: 32m ago         │ │ │
│ │ │                                                                        │ │ │
│ │ │ Thesis: Delivery miss expected. Margin compression risk. EV          │ │ │
│ │ │ competition intensifying. Valuation still expensive at 60x P/E.       │ │ │
│ │ │                                                                        │ │ │
│ │ │ Suggested Action: SELL 50% of position                                │ │ │
│ │ │ Risk Level: HIGH - Volatility expected                                │ │ │
│ │ │                                                                        │ │ │
│ │ │ [Execute Trade] [Add to Watchlist] [Share] [Dismiss]                  │ │ │
│ │ └────────────────────────────────────────────────────────────────────────┘ │ │
│ │                                                                            │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### Filter Bar
```yaml
Container:
  - Background: Surface (#1E293B)
  - Padding: 16px
  - Border-radius: lg (12px)
  - Margin-bottom: 16px

Dropdowns:
  - Width: 160px each
  - Height: 36px
  - Background: Background (#0F172A)
  - Border: 1px solid Border
  - Border-radius: md (8px)

Confidence Star Rating:
  - Stars: 5 circles
  - Filled: Primary color
  - Unfilled: Border color
  - Interactive: Click to set minimum

Applied Filters:
  - Pills with X button
  - Background: Primary 20% opacity
  - Padding: 4px 8px
  - Border-radius: full
```

#### Signal Card
```yaml
Container:
  - Background: Surface (#1E293B)
  - Border-radius: lg (12px)
  - Padding: 20px
  - Margin-bottom: 16px
  - Border-left: 4px solid type color

Signal Type Colors:
  - BUY: Secondary (#10B981)
  - SELL: Danger (#EF4444)
  - HOLD: Info (#6366F1)

Header Row:
  - Action Badge: BUY/SELL/HOLD, bold, 16px
  - Symbol: 18px bold, Primary color
  - Company Name: 14px, Text Secondary

Meta Row:
  - Agent name: 13px
  - Confidence bar: 100px width, 5 segments
  - Timestamp: "2m ago", 13px

Thesis Text:
  - Font: 14px
  - Color: Text Primary
  - Line-height: 1.6

Suggested Action Box:
  - Background: Surface Light
  - Padding: 12px
  - Border-radius: md
  - Margin: 12px 0

Action Buttons:
  - Execute Trade: Primary filled
  - Others: Secondary outlined
  - Height: 36px
  - Gap: 8px
```

---

## 5. Copy Trading

### Purpose
Browse and follow top-performing traders/agents, manage copied positions.

### Layout

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ COPY TRADING                                                  [My Copyed Trades]    │
├────────────────────────────────────────────────────────────────────────────────┤
│ YOUR COPY TRADING SUMMARY (Height: 160px)                                      │
│ ┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐     │
│ │ Following       │ Total P&L       │ Best Performer  │ Copy Trades     │     │
│ │                 │                 │                 │ (Active)        │     │
│ │ 3 traders       │ +$1,245.50      │ @AlphaKing      │ 8 positions     │     │
│ │                 │ (+3.2%)         │ +$847 (68%)     │                 │     │
│ │ [Manage]        │ [View Report]   │ [View Profile]  │ [Close All]     │     │
│ └─────────────────┴─────────────────┴─────────────────┴─────────────────┘     │
├────────────────────────────────────────────────────────────────────────────────┤
│ TOP PERFORMERS (Leaderboard)                                                   │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ Rank: [Top 10 ▼]  Period: [30 Days ▼]  Category: [All Assets ▼]          │ │
│ ├────────────────────────────────────────────────────────────────────────────┤ │
│ │                                                                            │ │
│ │ ┌──────┬──────────────┬─────────┬──────────┬──────────┬─────────────────┐ │ │
│ │ │ Rank │ Trader       │ Return  │ Win Rate │ AUM     │ Copy Action     │ │ │
│ ├──────┼──────────────┼─────────┼──────────┼──────────┼─────────────────┤ │ │
│ │ │ #1   │ @AlphaKing   │ +127.4% │ 78.2%    │ $2.4M   │ [Following ✓]   │ │ │
│ │ │      │ ████████████ │ 342 trades         │ 1,247 copiers │ [Profile] │ │ │
│ │ ├──────┼──────────────┼─────────┼──────────┼──────────┼─────────────────┤ │ │
│ │ │ #2   │ @TechBull    │ +94.2%  │ 71.5%    │ $1.8M   │ [Follow]        │ │ │
│ │ │      │ ██████████░░ │ 256 trades         │ 892 copiers   │ [Profile] │ │ │
│ │ ├──────┼──────────────┼─────────┼──────────┼──────────┼─────────────────┤ │ │
│ │ │ #3   │ @CryptoWhale │ +82.7%  │ 68.9%    │ $3.1M   │ [Following ✓]   │ │ │
│ │ │      │ █████████░░░ │ 412 trades         │ 2,103 copiers │ [Profile] │ │ │
│ │ ├──────┼──────────────┼─────────┼──────────┼──────────┼─────────────────┤ │ │
│ │ │ #4   │ @ValueHunter │ +67.3%  │ 74.1%    │ $950K   │ [Follow]        │ │ │
│ │ │      │ ████████░░░░ │ 189 trades         │ 534 copiers   │ [Profile] │ │ │
│ │ ├──────┼──────────────┼─────────┼──────────┼──────────┼─────────────────┤ │ │
│ │ │ #5   │ @MomentumPro │ +54.8%  │ 65.3%    │ $1.2M   │ [Follow]        │ │ │
│ │ │      │ ███████░░░░░ │ 298 trades         │ 721 copiers   │ [Profile] │ │ │
│ │ └──────┴──────────────┴─────────┴──────────┴──────────┴─────────────────┘ │ │
│ │                                                                            │ │
│ │ Pagination: [<] [1] [2] [3] [4] [5] [...] [20] [>]                         │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────┤
│ ACTIVE COPY POSITIONS                                                          │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ Trader          │ Position │ Entry    │ Current  │ P&L       │ Actions   │ │
│ ├─────────────────┼──────────┼──────────┼──────────┼───────────┼───────────┤ │
│ │ @AlphaKing      │ NVDA     │ $845.00  │ $890.00  │ +$252 +5% │ [Unfollow]│ │
│ │ @CryptoWhale    │ BTC      │ $65,200  │ $68,500  │ +$148 +5% │ [Unfollow]│ │
│ │ @AlphaKing      │ MSFT     │ $405.00  │ $420.00  │ +$127 +3% │ [Unfollow]│ │
│ │ @TechBull       │ AAPL     │ $168.50  │ $175.50  │ +$84 +4%  │ [Unfollow]│ │
│ └─────────────────┴──────────┴──────────┴──────────┴───────────┴───────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### Summary Cards
```yaml
Grid: 4 columns
Padding: 16px
Background: Surface
Border-radius: lg

Value:
  - Font: 24px bold
  - Color: Text Primary

Subtext:
  - Font: 14px
  - Color: Text Secondary
  - Percentage in color-coded parentheses

Action Button:
  - Style: Secondary outlined
  - Width: 100%
  - Height: 36px
```

#### Leaderboard Table
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 16px

Filter Bar:
  - 3 dropdowns inline
  - Margin-bottom: 16px

Table Columns:
  - Rank: 60px, centered, with medal icons (🥇🥈🥉)
  - Trader: 160px - Avatar + username + performance bar
  - Return: 100px - percentage + bar chart (10 segments)
  - Win Rate: 100px - percentage
  - AUM: 100px - currency formatted
  - Copy Action: 140px - Follow/Following button + Profile link

Performance Bar:
  - Width: 120px
  - Height: 6px
  - Background: Border
  - Fill: Primary gradient (width based on rank)

Following Badge:
  - Green checkmark icon
  - "Following" text, 13px
```

#### Active Positions Table
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Margin-top: 24px

Columns:
  - Trader: 120px - username link
  - Position: 80px - symbol, bold
  - Entry: 100px - monospace
  - Current: 100px - monospace
  - P&L: 120px - color-coded, percentage
  - Actions: 100px - Unfollow button

Row Height: 48px
Hover: Surface Light background
```

---

## 6. Backtest Interface

### Purpose
Run backtests with 7 different engines, analyze strategy performance.

### Layout

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ BACKTEST                                                       [Save Strategy] [Load] │
├────────────────────────────────────────────────────────────────────────────────┤
│ STRATEGY CONFIGURATION (Height: 200px)                                         │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ Strategy Name: [My Alpha Combo Strategy                        ]           │ │
│ │                                                                            │ │
│ │ Engine: [Vibe-Trading Multi-Factor ▼]  Data Feed: [Daily OHLCV ▼]         │ │
│ │                                                                            │ │
│ │ Assets: [BTC, ETH, NVDA, AAPL, MSFT                            ]          │ │
│ │         [+] Add more assets                                                │ │
│ │                                                                            │ │
│ │ Date Range: [Jan 1, 2024] to [Apr 1, 2025]  |  Initial Capital: $100,000  │ │
│ │                                                                            │ │
│ │ Alpha Factors (3 selected):                                               │ │
│ │ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            │ │
│ │ │ Momentum 12M [✕] │ │ Mean Reversion [✕]│ │ Volume Profile [✕]│           │ │
│ │ └──────────────────┘ └──────────────────┘ └──────────────────┘            │ │
│ │ [+] Browse Alpha Zoo (452 factors)                                       │ │
│ │                                                                            │ │
│ │ [▶ Run Backtest]                                         [Advanced Options▼] │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────┤
│ BACKTEST RESULTS (Shows after running)                                         │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ PERFORMANCE SUMMARY                                                        │ │
│ │ ┌───────────┬───────────┬───────────┬───────────┬───────────┬──────────┐  │ │
│ │ │ Total     │ Annual    │ Max       │ Sharpe    │ Win Rate  │ Total    │  │ │
│ │ │ Return    │ Return    │ Drawdown  │ Ratio     │           │ Trades   │  │ │
│ │ ├───────────┼───────────┼───────────┼───────────┼───────────┼──────────┤  │ │
│ │ │ +42.7%    │ +51.2%    │ -12.4%    │ 2.14      │ 64.3%     │ 247      │  │ │
│ │ │ [█████]   │ [█████]   │ [███]     │ [█████]   │ [████]    │          │  │ │
│ │ └───────────┴───────────┴───────────┴───────────┴───────────┴──────────┘  │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ EQUITY CURVE                                                             │ │
│ │ ┌────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ $145K ┤                                               ╭────────────   │ │ │
│ │ │       │                                          ╭───╯              │ │ │
│ │ │ $130K ┤              ╭───────────────────────────╮╯                  │ │ │
│ │ │       │         ╭───╯                            │                   │ │ │
│ │ │ $115K ┤────╭────╯                                │                   │ │ │
│ │ │       │    │                                     │                   │ │ │
│ │ │ $100K ┴────┴─────────────────────────────────────┴────────────────   │ │ │
│ │ │       Jan 1  Jan 15  Feb 1  Feb 15  Mar 1  Mar 15  Apr 1  Apr 15     │ │ │
│ │ │                                                                        │ │ │
│ │ │ ───── Strategy    █████ Benchmark (S&P 500)                           │ │ │
│ │ │                                                                        │ │ │
│ │ └────────────────────────────────────────────────────────────────────────┘ │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ MONTHLY RETURNS HEATMAP                                                  │ │
│ │ ┌────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │        │ Jan   │ Feb   │ Mar   │ Apr   │ May   │ Jun   │ ...          │ │ │
│ │ │ 2024   │ +5.2% │ +3.1% │ -1.4% │ +8.7% │ +2.3% │ +4.5% │              │ │ │
│ │ │        │ ████  │ ███   │ █     │ ██████│ ██    │ ████  │              │ │ │
│ │ │ 2025   │ +6.8% │ -2.1% │ +7.4% │ +3.9% │       │       │              │ │ │
│ │ │        │ █████ │ █     │ ██████│ ███   │       │       │              │ │ │
│ │ └────────────────────────────────────────────────────────────────────────┘ │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### Strategy Configuration Panel
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 20px

Form Fields:
  - Label: 13px bold, Text Secondary
  - Input: Background (#0F172A), Border, 40px height
  - Border-radius: md

Strategy Name:
  - Width: 100%
  - Font: 16px

Dropdowns:
  - Width: 240px
  - Display: Inline-block

Asset Input:
  - Tags input style
  - Each asset as pill badge
  - "+" button to add more

Date Range:
  - Two date pickers inline
  - Separator text between
  - Width: 180px each

Alpha Factors:
  - Pills with close button (X)
  - Background: Primary 20% opacity
  - Padding: 8px 12px
  - Margin: 4px

Run Button:
  - Primary filled
  - Width: 160px
  - Height: 40px
  - Play icon
```

#### Performance Summary Grid
```yaml
Grid: 6 columns
Padding: 16px
Background: Surface
Border-radius: lg

Metric Card:
  - Label: 12px, Text Secondary, uppercase
  - Value: 20px bold, Primary color
  - Visual Bar: 5 segments, filled based on percentile

Bar Quality:
  - Excellent (top 20%): 5 filled segments, green
  - Good (top 40%): 4 filled segments
  - Average: 3 filled segments
  - Below avg: 2 filled segments
  - Poor: 1 filled segment, red
```

#### Equity Curve Chart
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 20px
  - Height: 300px

Lines:
  - Strategy: Primary color (#3B82F6), 3px stroke
  - Benchmark: Secondary color (#10B981), 2px stroke, dashed

Grid:
  - Horizontal lines: Border color
  - Vertical lines: None
  - Y-axis labels: Currency, 5 levels
  - X-axis labels: Dates, 6-8 points

Legend:
  - Position: Bottom left
  - Format: Line sample + label text
  - Gap: 24px between items
```

#### Heatmap
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 20px

Table:
  - Row headers: Year, bold
  - Column headers: Month, abbreviated
  - Cell: Square, 60x60px

Cell Coloring:
  - Strong positive (+8%+): Dark green (#065F46)
  - Positive: Green (#10B981)
  - Slight positive: Light green (#34D399)
  - Neutral: Gray (#64748B)
  - Slight negative: Light red (#F87171)
  - Negative: Red (#EF4444)
  - Strong negative (-8%-): Dark red (#991B1B)

Cell Content:
  - Percentage: 12px, white text
  - Bar: Optional, based on preference toggle
```

---

## 7. Alpha Zoo Browser

### Purpose
Browse and search through 452 pre-built alpha factors.

### Layout

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ALPHA ZOO (452 Factors)                                      [+ Create Custom Factor] │
├────────────────────────────────────────────────────────────────────────────────┤
│ SEARCH & FILTERS                                                               │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ 🔍 Search alphas...                                         [Search]       │ │
│ │                                                                            │ │
│ │ Category: [All Categories ▼]  Difficulty: [All ▼]  Performance: [Any ▼]   │ │
│ │                                                                            │ │
│ │ Tags: [Momentum ●] [Mean-Reversion ●] [Volume ●] [Volatility ●]          │ │
│ │       [Machine Learning ○] [Statistical ○] [Fundamental ○]                │ │
│ │                                                         [Clear Filters]    │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────┤
│ ALPHA FACTORS GRID                                                             │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ View: [▦ Grid] [☰ List]  Sort: [Popularity ▼]  Show: [20 per page ▼]    │ │
│ ├────────────────────────────────────────────────────────────────────────────┤ │
│ │ ┌───────────────┬───────────────┬───────────────┬───────────────┐         │ │
│ │ │ Momentum 12M  │ Mean Reversion│ Volume Profile│ Volatility    │         │ │
│ │ │ ████████████  │ Skill: Adv.   │ Skill: Int.   │ Momentum      │         │ │
│ │ │ Skill: Basic  │ Win: 58.4%    │ Win: 61.2%    │ Skill: Adv.   │         │ │
│ │ │ Win: 64.2%    │ Sharpe: 1.84  │ Sharpe: 2.01  │ Win: 55.7%    │         │ │
│ │ │ Sharpe: 2.14  │ ───────────── │ ───────────── │ Sharpe: 1.67  │         │ │
│ │ │ ───────────── │ [Add to Strat]│ [Add to Strat]│ ───────────── │         │ │
│ │ │ [Add to Strat]│ [Preview]     │ [Preview]     │ [Add to Strat]│         │ │
│ │ │ [Preview]     │               │               │ [Preview]     │         │ │
│ │ └───────────────┴───────────────┴───────────────┴───────────────┘         │ │
│ │ ┌───────────────┬───────────────┬───────────────┬───────────────┐         │ │
│ │ │ RSI Divergence│ Bollinger Break│ MACD Cross   │ Sector Rotation│        │ │
│ │ │ Skill: Int.   │ Skill: Basic  │ Skill: Int.   │ Skill: Adv.   │         │ │
│ │ │ Win: 59.8%    │ Win: 54.2%    │ Win: 62.1%    │ Win: 57.4%    │         │ │
│ │ │ Sharpe: 1.78  │ Sharpe: 1.45  │ Sharpe: 1.92  │ Sharpe: 1.56  │         │ │
│ │ │ ───────────── │ ───────────── │ ───────────── │ ───────────── │         │ │
│ │ │ [Add to Strat]│ [Add to Strat]│ [Add to Strat]│ [Add to Strat]│         │ │
│ │ │ [Preview]     │ [Preview]     │ [Preview]     │ [Preview]     │         │ │
│ │ └───────────────┴───────────────┴───────────────┴───────────────┘         │ │
│ │                                                                            │ │
│ │ Pagination: [<] [1] [2] [3] [4] [5] [...] [23] [>]                         │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────┤
│ ALPHA PREVIEW MODAL (Overlay)                                                  │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ MOMENTUM 12M                                          [✕ Close]           │ │
│ │ ════════════════════════════════════════════════════════════════════════  │ │
│ │                                                                            │ │
│ │ Left Column (60%)                           Right Column (40%)            │ │
│ │ ┌─────────────────────────────┐            ┌─────────────────────────┐    │ │
│ │ │ DESCRIPTION                 │            │ METRICS                 │    │ │
│ │ │ Measures price momentum     │            │ Win Rate:    64.2%      │    │ │
│ │ │ over trailing 12 months,    │            │ Sharpe:      2.14       │    │ │
│ │ │ excluding most recent month.│            │ Max DD:      -8.4%      │    │ │
│ │ │                             │            │ Avg Trade:   +2.3%      │    │ │
│ │ │ Best for: Equity markets,   │            │ Profit Factor: 2.45     │    │ │
│ │ │ long-short portfolios       │            │                         │    │ │
│ │ │                             │            │ [██████████] perf bar   │    │ │
│ │ │ FORMULA                     │            │                         │    │ │
│ │ │ ─────────────────           │            │ USAGE                   │    │ │
│ │ │ (Return_{t-12} to t-2) /    │            │ ─────────               │    │ │
│ │ │ Volatility_{t-12}           │            │ Used in: 247 strategies │    │ │
│ │ │                             │            │ Copied by: 1,247 users  │    │ │
│ │ │ [Code snippet in mono]      │            │ Category: Momentum      │    │ │
│ │ └─────────────────────────────┘            │ Tags: momentum, equity, │    │ │
│ │                                            │ intermediate            │    │ │
│ │ [Add to Backtest] [Save to Favorites] [Share]                        │    │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### Search & Filter Section
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 20px
  - Margin-bottom: 20px

Search Input:
  - Width: 100%
  - Height: 44px
  - Search icon left
  - Font: 16px
  - Placeholder: "Search alphas by name, description, formula..."

Filter Row:
  - 3 dropdowns inline
  - Width: 200px each
  - Gap: 16px

Tags Section:
  - Display: Flex, wrap
  - Tag pills: 8px 12px padding
  - Active: Primary background
  - Inactive: Surface Light background
  - Border-radius: full
```

#### Alpha Card (Grid View)
```yaml
Card:
  - Width: 280px
  - Height: 220px
  - Background: Surface
  - Border-radius: lg
  - Padding: 16px
  - Border: 1px solid Border

Header:
  - Name: 16px bold, truncate
  - Difficulty: Skill level pill (Basic/Int/Adv)

Performance Bar:
  - 10 segments
  - Filled based on Sharpe ratio (normalized)
  - Color: Primary gradient

Metrics:
  - Win Rate: 13px, Text Secondary
  - Sharpe: 13px, Text Secondary
  - Margin: 4px each

Actions:
  - "Add to Strategy": Primary outline, full width
  - "Preview": Secondary outline, full width
  - Height: 32px
  - Margin-top: 12px
```

#### Preview Modal
```yaml
Overlay:
  - Background: Black 70% opacity
  - Click to close

Modal:
  - Background: Surface
  - Border-radius: xl (16px)
  - Padding: 32px
  - Max-width: 900px
  - Max-height: 80vh, overflow-y: auto

Close Button:
  - Position: Top right
  - Icon: X, 24x24
  - Hover: Surface Light

Layout:
  - 2-column grid (60% | 40%)
  - Gap: 32px

Description:
  - Section title: 14px bold, uppercase
  - Text: 14px, line-height 1.6

Formula Box:
  - Background: Background (#0F172A)
  - Padding: 12px
  - Border-radius: md
  - Font: 13px monospace

Metrics List:
  - Label: 13px, Text Secondary
  - Value: 16px bold, Primary
  - Gap: 12px between items

Action Buttons:
  - "Add to Backtest": Primary filled
  - Others: Secondary outlined
  - Gap: 8px
```

---

## 8. Portfolio

### Purpose
View portfolio positions, analytics, and export reports.

### Layout

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ PORTFOLIO                                              [Export Report] [Refresh Data] │
├────────────────────────────────────────────────────────────────────────────────┤
│ PORTFOLIO ANALYTICS (Height: 280px)                                            │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ Total Value: $102,450.00                                                   │ │
│ │ ─────────────────────────────────────────────────────────────────────────  │ │
│ │ $145K ┤                                               Current: $102,450   │ │
│ │       │                                          ╭────────────            │ │
│ │ $130K ┤                                      ╭────╯                        │ │
│ │       │                                  ╭───╯                            │ │
│ │ $115K ┤                          ╭───────╯                                │ │
│ │       │                      ╭───╯                                        │ │
│ │ $100K ┤──────────────────────╯                                            │ │
│ │       │                                                                   │ │
│ │  $85K ┴─────────────────────────────────────────────────────────────────   │ │
│ │       Jan 1   Jan 15   Feb 1   Feb 15   Mar 1   Mar 15   Apr 1   Apr 15   │ │
│ │                                                                            │ │
│ │ Day: [1D▼]  Return: +2.45%  |  Week: +4.12%  |  Month: +8.34%  |  All: +42.7%│ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────┤
│ ASSET ALLOCATION (Height: 250px)                                               │
│ ┌─────────────────────────────┬──────────────────────────────────────────────┐│
│ │ PIE CHART                   │ LEGEND                                        ││
│ │                             │ ┌──────────────────────────────────────────┐ ││
│ │      Stocks 65%             │ │ 🟦 Stocks        │ $66,593 │ 65.0% │    │ ││
│ │        ╭─────╮              │ │ ████████████████ │         │       │    │ ││
│ │    ╭───╯     ╰───╮          │ │ 🟩 Crypto        │ $25,857 │ 25.2% │    │ ││
│ │   │   Crypto    │          │ │ ████████░░░░░░░░ │         │       │    │ ││
│ │   │    25%      │          │ │ 🟨 Cash          │ $10,000 │  9.8% │    │ ││
│ │    ╰───╮     ╭───╯          │ │ ███░░░░░░░░░░░░░ │         │       │    │ ││
│ │      ╰─────╯                │ │                                          │ ││
│ │     Cash 10%                │ └──────────────────────────────────────────┘ ││
│ │                             │                                              ││
│ │ [Switch to Treemap]         │ Diversification Score: 7.4/10               ││
│ │                             │ ████████░░░░░░                              ││
│ └─────────────────────────────┴──────────────────────────────────────────────┘│
├────────────────────────────────────────────────────────────────────────────────┤
│ POSITIONS TABLE                                                                │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ [Select All] [Close Selected] [Rebalance]                                  │ │
│ ├────────────────────────────────────────────────────────────────────────────┤ │
│ │ ☐ Symbol │ Name         │ Type  │ Shares   │ Price   │ Value    │ P&L    │ │
│ ├──────────┼──────────────┼───────┼──────────┼─────────┼──────────┼────────┤ │
│ │ ☐ NVDA   │ NVIDIA       │ Stock │ 5.6      │ $890.00 │ $4,984   │ +9.0%  │ │
│ │ ☐ AAPL   │ Apple        │ Stock │ 12.0     │ $175.50 │ $2,106   │ +6.0%  │ │
│ │ ☐ MSFT   │ Microsoft    │ Stock │ 8.5      │ $420.00 │ $3,570   │ +8.0%  │ │
│ │ ☐ BTC    │ Bitcoin      │ Crypto│ 0.45     │ $68,500 │ $30,825  │ +7.3%  │ │
│ │ ☐ ETH    │ Ethereum     │ Crypto│ 2.1      │ $3,450  │ $7,245   │ +6.6%  │ │
│ │ ☐ SOL    │ Solana       │ Crypto│ 15.0     │ $145.00 │ $2,175   │ +12.4% │ │
│ │ ☐ USD    │ US Dollar    │ Cash  │ 10,000   │ $1.00   │ $10,000  │ 0.0%   │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────┤
│ TRADE HISTORY                                                                  │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ Date       │ Type │ Symbol │ Side │ Shares │ Price    │ Total    │ Agent  │ │
│ ├────────────┼──────┼────────┼──────┼────────┼──────────┼──────────┼────────┤ │
│ │ Apr 15 10:42│ BUY │ NVDA   │ Long │ 5.6    │ $889.50  │ $4,981   │Director│ │
│ │ Apr 14 14:23│ SELL│ TSLA   │ Long │ 3.2    │ $178.20  │ $570     │ Risk   │ │
│ │ Apr 13 09:15│ BUY │ BTC    │ Long │ 0.15   │ $67,800  │ $10,170  │ Quant  │ │
│ │ Apr 12 16:45│ BUY │ ETH    │ Long │ 1.0    │ $3,380   │ $3,380   │Director│ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### Portfolio Analytics Chart
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 20px
  - Height: 280px

Total Value Display:
  - Font: 32px bold, JetBrains Mono
  - Color: Text Primary
  - Margin-bottom: 20px

Chart Area:
  - Type: Area chart with gradient
  - Line: Primary, 3px stroke
  - Fill: Primary, 20% to 0% gradient
  - Grid: Horizontal only, Border color

Time Stats Bar:
  - Position: Bottom
  - Display: Flex, gap 24px
  - Each stat: Label (12px) + Value (14px bold)
  - Clickable periods with dropdown
```

#### Asset Allocation Section
```yaml
Grid: 2 columns (400px | remaining)
Gap: 24px

Pie Chart Container:
  - Height: 250px
  - Position: Relative
  - Toggle: "Switch to Treemap" button bottom left

Pie Segments:
  - Stocks: Primary (#3B82F6)
  - Crypto: Secondary (#10B981)
  - Cash: Warning (#F59E0B)
  - Labels: Percentage inside segment

Legend Table:
  - Row height: 40px
  - Asset class: Icon + name
  - Bars: 16 segments, filled by percentage
  - Value: Monospace, right-aligned
  - Percentage: 13px

Diversification Score:
  - Score: 16px bold
  - Bar: 16 segments, fill based on score / 10
```

#### Positions Table
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 16px
  - Margin-top: 24px

Toolbar:
  - Checkbox: "Select All"
  - Buttons: "Close Selected", "Rebalance"
  - Margin-bottom: 12px

Columns:
  - Checkbox: 40px
  - Symbol: 100px, bold, Primary color
  - Name: 160px
  - Type: 80px, pill badge (Stock/Crypto/Cash)
  - Shares: 100px, monospace, right-aligned
  - Price: 100px, monospace, right-aligned
  - Value: 120px, monospace, right-aligned
  - P&L: 100px, color-coded, percentage

Type Badges:
  - Stock: Blue background 20%
  - Crypto: Purple background 20%
  - Cash: Green background 20%
  - Border-radius: md
  - Padding: 4px 8px
```

#### Trade History Table
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Margin-top: 24px

Columns:
  - Date: 120px, 13px
  - Type: 80px, pill (BUY/SELL/HOLD)
  - Symbol: 80px, bold
  - Side: 60px, Long/Short
  - Shares: 100px, monospace
  - Price: 100px, monospace
  - Total: 100px, monospace
  - Agent: 100px, badge

Row Height: 40px
Hover: Surface Light
```

---

## 9. Settings

### Purpose
Configure API keys, broker connections, agent preferences, and application settings.

### Layout

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ SETTINGS                                                                       │
├────────────────────────────────────────────────────────────────────────────────┤
│ SETTINGS NAVIGATION (Tabbed Sidebar)                                           │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ [🔑 API Keys]           [Connected: 3/6]                                   │ │
│ │ [🏦 Brokers]            [Connected: 2/4]                                   │ │
│ │ [🧠 LLM Model]          [Current: Llama-3.3-70B]                           │ │
│ │ [🤖 Agents]             [Active: 4/4]                                      │ │
│ │ [📊 Display]                                                               │ │
│ │ [🔔 Notifications]                                                         │ │
│ │ [💾 Data & Storage]                                                        │ │
│ │ [🔐 Security]                                                              │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────┤
│ API KEYS PANEL (Active)                                                        │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ NVIDIA NIM API                                                             │ │
│ │ ─────────────────────────────────────────────────────────────────────────  │ │
│ │ API Key: [••••••••••••••••••••••••••••••••          ] [Show] [Test]       │ │
│ │ Status: [🟢 Connected]  |  Usage Today: $2.47  |  Requests: 1,247         │ │
│ │ Base URL: https://integrate.api.nvidia.com/v1                             │ │
│ │                                                                            │ │
│ │  Securities                                                          │ │
│ │ ─────────────────────────────────────────────────────────────────────────  │ │
│ │ API Key:    [•••••••••••••••••••                      ] [Show] [Test]      │ │
│ │ API Secret: [••••••••••••••••••••••••••••••••••••    ] [Show]             │ │
│ │ Environment: ( ) Paper Trading  ( ) Live Trading                           │ │
│ │ Status: [🟢 Paper Connected]  |  Account: $100,000 simulated               │ │
│ │                                                                            │ │
│ │ Binance                                                                    │ │
│ │ ─────────────────────────────────────────────────────────────────────────  │ │
│ │ API Key:    [                                          ] [Show] [Test]      │ │
│ │ API Secret: [                                          ] [Show]             │ │
│ │ Status: [⚪ Not Configured]                                                 │ │
│ │                                                                            │ │
│ │ GitHub (for signal sync)                                                   │ │
│ │ ─────────────────────────────────────────────────────────────────────────  │ │
│ │ Token: [••••••••••••••••••••••••••••••••          ] [Show] [Test]         │ │
│ │ Status: [🟢 Connected]  |  Gists: 12 active signals                        │ │
│ │                                                                            │ │
│ │ [+ Add API Key]  [Save All Changes]                                        │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### Settings Navigation
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 12px
  - Margin-bottom: 20px

Navigation Items:
  - Display: Flex, space-between
  - Padding: 12px 16px
  - Border-radius: md
  - Hover: Surface Light
  - Active: Primary background 10%

Item Structure:
  - Icon: 20x20px
  - Label: 14px
  - Status badge: Right side, small pill
```

#### API Key Section
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 24px
  - Margin-bottom: 16px

Section Header:
  - Font: 18px bold
  - Border-bottom: 2px solid Border
  - Padding-bottom: 12px
  - Margin-bottom: 16px

Form Fields:
  - Label: 13px bold, margin-bottom 4px
  - Input: Width 100%, height 40px
  - Background: Background
  - Border: 1px solid Border
  - Border-radius: md
  - Padding: 8px 12px

API Key Input:
  - Font-family: Monospace
  - Letter-spacing: 2px
  - Masked: bullets by default

Show Button:
  - Icon: Eye / Eye-off
  - Position: Right of input
  - Size: 32x32px

Test Button:
  - Secondary outline
  - marginLeft: 8px

Status Line:
  - Dot indicator: Green/Yellow/Red
  - Text: 13px
  - Gap: 16px between items

Radio Group (Environment):
  - Display: Inline-flex
  - Label + Radio button
  - Gap: 8px
```

#### Other Settings Panels (Summarized)

**LLL Model Panel:**
```yaml
- Model dropdown for each agent
- Sliders: Temperature, Max Tokens, Timeout
- Cost estimator per model
- Test connection button
- Model comparison table
```

**Agents Panel:**
```yaml
- Toggle switches for each agent
- Priority order drag-and-drop
- Per-agent configuration expand/collapse
- Reset to defaults button
```

**Display Panel:**
```yaml
- Theme selector (Dark/Light/System)
- Chart type preferences
- Default dashboard layout
- Timezone selector
- Date format selector
```

**Notifications Panel:**
```yaml
- Toggle notifications: Email, Push, In-app
- Event triggers: Trade executed, Signal generated, Risk alert
- Quiet hours: Time range picker
- Test notification button
```

**Trading Caps & Risk Limits Panel:**
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 24px

Section Header:
  - Title: "Trading Caps & Risk Limits"
  - Icon: Shield
  - Status badge: "Active" (green) or "Disabled" (gray)

Active Configuration Display:
  - Background: Blue 10% opacity
  - Grid layout showing current limits:
    * Max Position: $5,000
    * Max %: 20%
    * Daily Loss Limit: $2,000
    * Daily Loss %: 5%
  - Enforcement mode badge: "Hard Limit" or "Soft Limit"

Position Limits Section:
  Max Position Amount ($):
    - Type: Number field
    - Placeholder: "e.g., 5000"
    - Icon: DollarSign
    - Help text: "Maximum dollars per trade"
    - Min: 0

  Max Position Percentage (%):
    - Type: Number field
    - Placeholder: "e.g., 20"
    - Icon: Percent
    - Help text: "Percentage of portfolio per trade"
    - Min: 0, Max: 100

Daily Loss Limits Section:
  Daily Loss Limit ($):
    - Type: Number field
    - Placeholder: "e.g., 2000"
    - Help text: "Stop trading after this loss"

  Daily Loss Percentage (%):
    - Type: Number field
    - Placeholder: "e.g., 5"
    - Help text: "Stop trading after % loss"
    - Min: 0, Max: 100

Enforcement Mode Section:
  - Border-top separator
  - Title: "Enforcement Mode"
  - Radio button group:
    * Hard Limit (selected by default)
      - Description: "Block any trade that exceeds caps"
      - Color: Red indicator
    * Soft Limit
      - Description: "Warn but allow trades (for testing)"
      - Color: Yellow indicator

  Enable Toggle:
    - Checkbox: "Enable trading caps"
    - Position: Below enforcement options

Action Button:
  - "Save Trading Caps" (Primary, blue, full width)
  - Loading state: "Saving..."

Info Box:
  - Background: Blue 10% opacity
  - Recommendation text:
    "Set max position to 10-20% of portfolio and daily
     loss limit to 5%. This prevents catastrophic losses
     while allowing room for growth."

Validation Rules:
  - At least one limit must be set
  - Error message if all fields empty
  - Success toast on save
  - Confirmation if caps are very restrictive
```

**Market Data Providers Panel:**
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 24px

Section Header:
  - Title: "Market Data Providers"
  - Icon: TrendingUp
  - Subtitle: "Configure free market data APIs"

CoinGecko Status Box:
  - Background: Green 10% opacity
  - Badge: "✓ Active (Free, No Key)"
  - Description: "Real-time crypto prices, market caps, gainers/losers"
  - Always visible, no configuration needed

Alpha Vantage Section:
  - Title: "Alpha Vantage" + Info button
  - API Key field (password type)
  - Test button
  - Status indicator: "Connected" / "Failed"
  - Info Modal contains:
    * What is Alpha Vantage
    * Free tier limits (5/min, 500/day)
    * Step-by-step setup guide
    * Direct signup link: alphavantage.co
    * What you get: stocks, forex, sentiment

Finnhub Section:
  - Title: "Finnhub" + Info button
  - API Key field
  - Test button
  - Status indicator
  - Info Modal:
    * What is Finnhub
    * Free tier (60/min)
    * Setup steps
    * Signup link: finnhub.io
    * Features: real-time stocks, news, SEC filings

Twelve Data Section:
  - Title: "Twelve Data" + Info button
  - API Key field
  - Info Modal with setup guide

FRED (Economic Data) Section:
  - Title: "FRED" + Info button
  - API Key field
  - Info Modal: Federal Reserve economic data

Save Button:
  - "Save Market Data Settings" (Primary, full width)

Info Box:
  - "CoinGecko is always active - no setup required"
  - "Add other providers for more data coverage"
```

**Email Service (SendGrid) Panel:**
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 24px

Section Header:
  - Title: "Email Notifications (SendGrid)"
  - Icon: Mail
  - Status badge: "Enabled" / "Disabled"
  - Info button opens setup modal

Form Fields:
  SendGrid API Key:
    - Type: Password field
    - Placeholder: "SG.xxxxxxxxxx..."
    - Help text: "From SendGrid dashboard"

  From Email:
    - Type: Email field
    - Placeholder: "your@email.com"
    - Help text: "Sender email address"

  Enable Toggle:
    - Checkbox: "Enable email notifications"

Test Section (shown when enabled):
  - Test Email Address field
  - "Send Test" button with Send icon
  - Success message after sending

Save Button:
  - "Save Email Settings" (Primary, blue)

Info Box:
  - Email templates included
  - Trade confirmations, price alerts, daily summaries

Info Modal Contents:
  - What is SendGrid
  - FREE tier: 100 emails/day forever
  - Complete setup guide:
    1. Go to sendgrid.com/signup
    2. Create free account
    3. Verify email
    4. Create API key (Full Access)
    5. Copy key (starts with "SG.")
    6. Paste above
  - Email templates preview
  - Important: Verify sender email
```

**Discord Bot Panel:**
```yaml
Container:
  - Background: Surface
  - Border-radius: lg
  - Padding: 24px

Section Header:
  - Title: "Discord Bot (Two-Way Chat)"
  - Icon: MessageSquare
  - Status badge: "Running" (green) / "Stopped" (gray)
  - Info button opens complete setup guide

Connection Status Box (when enabled):
  - Background: Green 10% opacity
  - "Bot Connected" with checkmark
  - Server ID displayed
  - Channel ID displayed

Form Fields:
  Bot Token:
    - Type: Password field
    - Show/Hide toggle
    - Help text: "From Discord Developer Portal → Bot → Reset Token"
    - Warning: "Only shown once!"

  Server ID (Guild ID):
    - Type: Text field (numeric)
    - Placeholder: "123456789012345678"
    - Help text: "Enable Developer Mode → Right-click server → Copy ID"

  Channel ID:
    - Type: Text field (numeric)
    - Placeholder: "123456789012345678"
    - Help text: "Right-click channel → Copy ID"

Enable Options:
  - Checkbox: "Enable Discord bot"
  - Checkbox (indented): "Enable two-way chat (AI responses)"

Test Section:
  - Test Message field
  - "Send" button
  - Success confirmation

Action Buttons:
  - "Start Bot" (Primary, Discord purple #5865F2)
  - "Save Settings" (Secondary)

Available Commands Box:
  - Background: Discord purple 10% opacity
  - Commands listed:
    * !portfolio - Portfolio summary
    * !trades - Recent trades
    * !help - Show commands
    * !status - Bot status
  - Code font for command names

Info Modal (Complete 5-Step Guide):
  Step 1: Create Discord Application
    - discord.com/developers/applications
    - New Application → Name → Create
    - Bot → Add Bot

  Step 2: Get Bot Token
    - Reset Token → Copy immediately
    - Warning: Only shown once!

  Step 3: Add Bot to Server
    - OAuth2 → URL Generator
    - Scopes: bot, applications.commands
    - Permissions list
    - Copy URL → Open in browser → Authorize

  Step 4: Get Server & Channel IDs
    - Enable Developer Mode
    - Right-click → Copy ID

  Step 5: Start Bot
    - Enable checkbox
    - Click Start Bot
    - Test with !help

  Security Warning:
    - Never share bot token
    - Reset if exposed

  Available Commands Reference
```

**Data & Storage Panel:**
```yaml
- Data directory path + browse button
- Clear cache button
- Export data button
- Auto-backup toggle (Google Drive / GitHub Gists)
- Storage usage indicator
```

**Security Panel:**
```yaml
- Change app password
- API auth key rotation
- Session management
- 2FA setup (optional)
- Logout all devices button
```

---

## Mobile Responsive Breakpoints

### Tablet (768px - 1024px)
```yaml
- Sidebar: Collapsed by default, toggle to expand
- Grid layouts: 2 columns instead of 4
- Tables: Horizontal scroll
- Charts: Reduced height
- Modals: Full width with padding
```

### Mobile (320px - 767px)
```yaml
- Layout: Single column, stacked
- Navigation: Bottom tab bar
- Header: Simplified, hamburger menu
- Cards: Full width with padding
- Tables: Card-based layout (one row = one card)
- Charts: Touch-optimized interactions
- Inputs: 48px minimum touch targets
- Bottom sheet for modals
```

### Mobile Navigation Structure
```
┌─────────────────────────────────┐
│ HEADER (Hamburger + Title)      │
├─────────────────────────────────┤
│                                 │
│      MAIN CONTENT AREA          │
│                                 │
├─────────────────────────────────┤
│ [📊]  [🤖]  [📡]  [👥]  [⚙️]   │
│ Dash  Agents Signals Copy  Set  │
└─────────────────────────────────┘
```

---

## Interaction Patterns

### Common Interactions

#### Dropdown Menus
```yaml
Trigger: Click on chevron
Animation: 200ms fade + slide down
Position: Below trigger, left-aligned
Backdrop: None for simple, scrim for modal
Close: Click outside, Escape, select item
```

#### Toast Notifications
```yaml
Position: Bottom right (desktop), Top (mobile)
Width: 320px (desktop), Full (mobile)
Duration: 4000ms auto-dismiss
Types: Success (green), Error (red), Info (blue), Warning (amber)
Stacking: Vertical, max 3 visible
Animation: Slide in from right
```

#### Loading States
```yaml
Skeleton screens for initial load
Spinner for actions (24px default)
Progress bar for long operations
Shimmer effect for content placeholders
```

#### Confirmation Dialogs
```yaml
Overlay: Black 50% opacity
Modal: Centered, max-width 400px
Title: Bold, 18px
Message: 14px, line-height 1.5
Actions: Cancel (left), Confirm (right, red for destructive)
```

---

## Accessibility Requirements

### Keyboard Navigation
```yaml
Tab order: Logical left-to-right, top-to-bottom
Focus indicators: 2px outline, Primary color
Skip links: At top of page
Shortcut: ⌘K for command palette
```

### Screen Reader Support
```yaml
ARIA labels on all interactive elements
Live regions for real-time updates
Alt text on images and charts (data summaries)
Heading hierarchy: H1 → H2 → H3
```

### Color Contrast
```yaml
Normal text: 4.5:1 minimum ratio
Large text: 3:1 minimum ratio
UI components: 3:1 minimum ratio
Never use color alone to convey information
```

---

## Export Notes

These wireframes are designed to be implementation-ready specifications. Key considerations:

1. **Component-based architecture**: Each section maps to a React component
2. **Responsive by default**: All layouts adapt to screen size
3. **Real-time updates**: WebSocket connections for live data
4. **Performance**: Virtual scrolling for long lists, memoized charts
5. **PWA ready**: Offline support, install prompts, push notifications

Use this document alongside the plan.md to build the frontend systematically, screen by screen.