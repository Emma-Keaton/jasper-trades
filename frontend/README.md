<div align="center">
  <img width="1200" height="475" alt="Jasper Trades Banner" src="/logo.png" />
</div>

# Jasper Trades - Frontend

AI-powered trading dashboard built with Next.js 15, React 19, and Tailwind CSS v4.

## Features

- 🤖 Real-time AI agent status monitoring
- 📊 Live portfolio tracking with auto-refresh
- 📈 Interactive equity charts with multiple timeframes
- 🔄 Copy trading interface
- 🧪 Backtesting dashboard
- 📱 PWA support for mobile devices
- ⚡ Real-time WebSocket updates

## Prerequisites

- Node.js 18+ (recommended: 20+)
- Backend API running (see [backend README](../backend/README.md))

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

Update the variables in `.env.local`:

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# WebSocket URL (optional, defaults to API URL)
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

> AI features (Gemini primary / NVIDIA NIM fallback) run on the **backend**.
> Configure `GEMINI_API_KEYS` and `NVIDIA_API_KEY` in `backend/.env` (see root `DEPLOYMENT.md`),
> not the frontend — no `NEXT_PUBLIC_*` AI keys are read by this app.

### 3. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Build for Production

```bash
npm run build
npm start
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run lint` - Run ESLint
- `npm run clean` - Clean Next.js cache

## AI Integration

AI features run on the **backend** with a dual-provider proxy:
**Gemini 2.5 Flash is the primary LLM** (multi-key rotation via `GEMINI_API_KEYS`);
**NVIDIA NIM is the automatic fallback** (`NVIDIA_API_KEY`). Task-tier model routing:

- **Executions / risk checks**: `nvidia/nemotron-mini-4b-instruct`
- **Analysis / news / sentiment / copy trading**: `meta/llama-3.1-8b-instruct`
- **Portfolio / deep reasoning**: `nvidia/llama-3.3-nemotron-super-49b-v1`
- **Ensemble (background)**: `openai/gpt-oss-20b`

Get an NVIDIA key from: https://build.nvidia.com/ (only needed to use NVIDIA as fallback).
See root `DEPLOYMENT.md` for the full env setup.

## Project Structure

```
frontend/
├── app/
│   ├── globals.css       # Global styles (Tailwind v4)
│   ├── layout.tsx        # Root layout with metadata
│   └── page.tsx          # Main trading dashboard
├── components/
│   ├── DashboardTab.tsx  # Main dashboard view
│   ├── AgentsTab.tsx     # Agent configuration
│   ├── SignalsTab.tsx    # Signal feed
│   ├── CopyTradeTab.tsx  # Copy trading UI
│   ├── BacktestTab.tsx   # Backtesting interface
│   ├── AlphaZooTab.tsx   # Alpha factors browser
│   ├── PortfolioTab.tsx  # Portfolio management
│   └── SettingsTab.tsx   # Settings panel
├── lib/
│   ├── api-client.ts     # Backend API client
│   ├── websocket.ts      # WebSocket connection
│   └── utils.ts          # Utility functions
├── hooks/
│   └── use-mobile.ts     # Mobile detection hook
├── assets/
│   └── image/
│       └── logo.png      # Jasper Trades logo
├── public/
│   ├── logo.png          # Logo
│   ├── favicon.ico       # Favicon
│   ├── icon-192.png      # PWA icon
│   ├── icon-512.png      # PWA icon
│   ├── apple-touch-icon.png
│   └── manifest.json     # PWA manifest
├── package.json
├── tsconfig.json
├── next.config.ts
└── tailwind.config.ts
```

## CSS Framework

This project uses **Tailwind CSS v4** with the new CSS-first configuration:

- Zero configuration required
- CSS variables for theme customization
- Automatic optimization via PostCSS
- See `app/globals.css` for theme variables

## PWA Support

The app is PWA-ready with:
- Offline support
- Install prompt
- Mobile-optimized shortcuts
- Apple touch icons

## License

AGPL-3.0