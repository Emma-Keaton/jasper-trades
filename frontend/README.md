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

# NVIDIA NIM API Key (for frontend AI features)
NEXT_PUBLIC_NVIDIA_API_KEY=your_nvidia_api_key_here
```

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

This frontend uses **NVIDIA NIM API** for AI-powered features:

- **Llama-3.2-3B-Instruct**: Fast risk checks and order execution (~50-100ms)
- **Llama-3.3-70B-Instruct**: News analysis and signal generation (~200-400ms)
- **Llama-3.1-8B-Instruct**: Copy trading decisions (~100-150ms)
- **Nemotron-3-Super-120B**: Complex portfolio analysis (~500-800ms)

Get your NVIDIA API key from: https://build.nvidia.com/

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