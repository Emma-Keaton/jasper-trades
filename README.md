# Jasper Trades - AI-Powered Trading Platform

**Your complete trading solution with AI chat, multi-broker execution, free market data, email/Discord notifications, and risk management.**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org/)

## 🚀 Quick Start

```bash
install.bat    # Install dependencies
start.bat      # Run app
```

Opens: http://localhost:3000

---

## ✨ Features

### 🤖 AI Trading Assistant
- **4-Stage Agent Pipeline**: Director → Quant → Risk → Execution
- **WhatsApp AI Chat**: "Should I buy AAPL?", "Portfolio status", "Why sell TSLA?"
- **NVIDIA NIM API**: Llama-3.2-3B (fast), Llama-3.3-70B (deep analysis), Nemotron-120B (portfolio)
- **Multi-Model Routing**: Cheapest/fastest model per task

### 🏦 Multi-Broker Execution
Auto-routes trades by asset class:

| Asset Class | Broker |
|-------------|--------|
| Stocks/Equities | Alpaca |
| Crypto | Binance |
| Forex/CFD | Exness (MT5) |
| Futures/Forex | IBKR |
| Solana Tokens | Solana broker |

### 📊 Free Market Data
- **CoinGecko**: Real-time crypto prices (no API key needed!)
- **Alpha Vantage**: Stocks, forex, news sentiment (FREE 500/day)
- **Finnhub**: Real-time US stocks (FREE 60/min)
- **Twelve Data**: 800 calls/day free
- **FRED**: Economic data (GDP, Treasury yields)

### 📧 Notifications & Chat
- **WhatsApp**: Embedded OpenWA (no external service)
- **Discord Bot**: Two-way chat with commands (`!portfolio`, `!trades`, `!help`)
- **Email (SendGrid)**: 100 emails/day free - trade confirmations, daily summaries
- **Slack, Telegram**: Webhook support

### 🛡️ Risk Management
- **Trading Caps**: Max position $, max %, daily loss limits
- **Circuit Breaker**: Auto-halt on flash crashes, volatility spikes
- **Hard/Soft Limits**: Block or warn on cap breaches
- **Real-Time Dashboard**: VaR, drawdown, correlation heatmap

### 💰 Auto-Payout System
- **Daily Profit Distribution**: 50% of profits (customizable)
- **Multi-Currency**: USDT (ERC20, TRC20, SOLANA)
- **Tatum Integration**: Blockchain transfers
- **Fee Calculation**: Auto-deducts network fees

### 📈 Advanced Analytics
- **452 Alpha Factors**: Quantitative signals library
- **Backtesting**: Historical performance testing
- **Ensemble/Swarm**: Multi-LLM consensus
- **Kronos Colab**: GPU-accelerated model training

---

## 🎯 What's Included

### Backend (FastAPI + Python 3.11+)
- ✅ Real-time trading engine
- ✅ 4-stage AI agent pipeline
- ✅ Multi-broker integration (Alpaca, Binance, Exness, IBKR)
- ✅ Risk management & circuit breakers
- ✅ WhatsApp/Discord/Email notifications
- ✅ Free market data providers
- ✅ Auto-payout system
- ✅ Backtesting & alpha factors

### Frontend (Next.js 15 + React 19 + Tailwind CSS v4)
- ✅ Trading dashboard with real-time PnL
- ✅ Portfolio analytics
- ✅ Settings page for all integrations
- ✅ Withdrawal management
- ✅ Mobile responsive design

### Services (40+ modules)
- Market data providers (CoinGecko, Alpha Vantage, Finnhub)
- Email service (SendGrid - 100/day free)
- Discord bot (two-way chat)
- WhatsApp service (embedded OpenWA)
- Exness/MT5 integration
- Withdrawal service (Tatum blockchain)
- Circuit breaker system
- AI chat assistant
- Experience buffer (reinforcement learning)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15, React 19, Tailwind CSS v4, TypeScript |
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy, SQLite |
| **AI/LLM** | NVIDIA NIM API (Llama-3.2-3B, Llama-3.3-70B, Nemotron-120B) |
| **Brokers** | Alpaca, Binance, Exness (MT5), IBKR |
| **Market Data** | CoinGecko (free), Alpha Vantage, Finnhub, Twelve Data |
| **Notifications** | WhatsApp (OpenWA), Discord Bot, SendGrid (email), Slack, Telegram |
| **Blockchain** | Tatum (USDT transfers), Solana |
| **Analytics** | DuckDB, QuantLib, TA-Lib |

---

## 📦 Installation

### Prerequisites
- **Node.js 18+** - [Download](https://nodejs.org/)
- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Git** (optional)

### Quick Install
```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/jasper-trades.git
cd jasper-trades

# Install dependencies
install.bat

# Optional: Install MT5 (Windows only, for Exness trading)
# Download from https://www.exness.com/
```

### Configure API Keys

**Required:**
- **NVIDIA NIM API** - AI/LLM (FREE $25/month credits)
  - Get key: https://catalog.ngc.nvidia.com/api-keys

**Optional (all FREE):**
- **CoinGecko** - Crypto prices ✅ No key needed!
- **Alpha Vantage** - Stocks/forex (500 calls/day free)
- **Finnhub** - Real-time stocks (60/min free)
- **SendGrid** - Email (100/day free)
- **Discord Bot** - Two-way chat (unlimited free)
- **Alpaca** - Paper trading (unlimited free)

Configure all keys in **Settings page** after first run!

---

## 🚀 Deployment

### Free Cloud Hosting

**Frontend:** Vercel (unlimited free)
**Backend:** Render (free tier 500 hours/month)
**WhatsApp:** Embedded (no external service)

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for complete guide including:
- Step-by-step Vercel/Render setup
- All free API key signup links
- Exness/MT5 configuration
- Discord bot creation
- SendGrid email setup
- Trading caps configuration

### Local Development
```bash
start.bat  # Runs both backend & frontend
```

- Backend: http://localhost:8000 (API docs: /docs)
- Frontend: http://localhost:3000

---

## 📚 Documentation

| Doc | Description |
|-----|-------------|
| **[DEPLOYMENT.md](DEPLOYMENT.md)** | Complete deployment guide + all free API keys |
| **[INSTALL.md](INSTALL.md)** | Local installation & troubleshooting |
| **[SETTINGS_API_KEYS.md](SETTINGS_API_KEYS.md)** | All API keys explained |
| **[PRODUCTION_READY.md](PRODUCTION_READY.md)** | Production checklist |

---

## 🔐 Security

- ✅ All API keys encrypted (AES-256) before database storage
- ✅ HTTPS in production
- ✅ Environment variables for secrets
- ✅ No hardcoded credentials
- ✅ Input validation & sanitization
- ✅ Rate limiting on API endpoints

---

## 🎓 Perfect For

- **Individual traders** - Automate your trading strategy
- **Quant developers** - 452 alpha factors + backtesting
- **Hobbyists** - Learn AI trading with free tools
- **Portfolios** - Multi-broker, multi-asset support
- **Students** - Free tier everything, no credit card needed

---

## 🗺️ Roadmap

### Phase 1 (Current) ✅
- [x] Multi-broker trading (Alpaca, Binance, Exness)
- [x] AI chat assistant (WhatsApp, Discord, Email)
- [x] Risk management (Trading caps, circuit breaker)
- [x] Free market data (CoinGecko, Alpha Vantage, Finnhub)
- [x] Auto-payout system (50% daily profit)

### Phase 2 (Next)
- [ ] Multi-model ensemble
- [ ] Twitter/Reddit sentiment analysis
- [ ] Smart order routing
- [ ] Copy trading leaderboards

### Phase 3 (Planned)
- [ ] Reinforcement learning
- [ ] On-chain analytics
- [ ] Portfolio optimizer
- [ ] Strategy marketplace

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file

---

## 💬 Support

- **Documentation**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Issues**: GitHub Issues
- **Discord**: [Join our server](YOUR_DISCORD_LINK)

---

## 🙏 Acknowledgments

Built with:
- [NVIDIA NIM API](https://catalog.ngc.nvidia.com/) - LLM inference
- [CoinGecko](https://www.coingecko.com/) - Crypto data (FREE!)
- [Alpha Vantage](https://www.alphavantage.co/) - Market data
- [Finnhub](https://finnhub.io/) - Real-time stocks
- [SendGrid](https://sendgrid.com/) - Email notifications
- [Discord.py](https://discordpy.readthedocs.io/) - Discord bot
- [Next.js](https://nextjs.org/) - Frontend framework
- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework

---

**📈 Ready to trade? [Get Started](#quick-start)**

**🎓 Questions? Check [INSTALL.md](INSTALL.md) or [DEPLOYMENT.md](DEPLOYMENT.md)**

**🚀 Deploy free version in 30 minutes → [DEPLOYMENT.md](DEPLOYMENT.md)**

**Jasper Trades** - Built with Next.js 15, FastAPI, NVIDIA NIM API