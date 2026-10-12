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

> AI features (Groq) run on the **backend**.
> Configure `GROQ_API_KEY` in `backend/.env` (see root `DEPLOYMENT.md`),
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

AI features run on the **backend** with Groq multi-key rotation (`GROQ_API_KEY`). Task-tier model routing:

- **Executions / risk checks / fast tasks**: `qwen/qwen3.8-27b`
- **Analysis / news / sentiment / copy trading / portfolio / deep**: `openai/gpt-oss-120b`
- **Ensemble (background)**: `openai/gpt-oss-20b`

Get a free key from: https://console.groq.com/keys
See root `DEPLOYMENT.md` for the full env setup.

## Project Structure

```
frontend/
├── app/
│   ├── globals.css       # Global styles (Tailwind v4)
│   ├── layout.tsx        # Root layout with metadata
│   └── page.tsx          # Main trading dashboard
├── components/
│   ├── screens/          # Tab views (Home, Trades, Markets, Signals, etc.)
│   ├── settings/         # Settings panels + setup guides
│   ├── portfolio/        # Wallet connect, portfolio widgets
│   ├── onboarding/       # Welcome wizard + tours
│   └── agents/           # Agent config
├── lib/
│   ├── api-client.ts     # Backend API client (auto device ID header)
│   ├── deviceFingerprint.ts # Persistent device ID
│   ├── websocket.ts      # WebSocket connection
│   └── utils.ts          # Utility functions
├── hooks/
│   └── use-mobile.ts     # Mobile detection hook
├── public/
│   ├── logo.png          # Logo
│   ├── favicon.ico       # Favicon
│   ├── icon-192.png      # PWA icon
│   ├── icon-512.png      # PWA icon
│   ├── apple-touch-icon.png
│   └── manifest.json     # PWA manifest
├── package.json
├── tsconfig.json
└── next.config.js
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
