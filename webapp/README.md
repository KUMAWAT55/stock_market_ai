# TradeIQ React Web App

React + Vite frontend for the TradeIQ intraday platform.

## Prerequisites

- Node.js 18+ (recommended 20+)
- Backend API running at `http://127.0.0.1:8000` (or set `VITE_API_BASE_URL`)

## Setup

```bash
cd webapp
cp .env.example .env
npm install
npm run dev
```

Open:
- `http://127.0.0.1:5173`

## Build

```bash
npm run build
npm run preview
```

## Key Features

- Full website routing: Home, About, Contact, Login, Register, Dashboard
- Protected dashboard route with backend auth APIs
- Live candlestick chart with EMA overlays
- Multi-timeframe prediction matrix
- Indicator heatmap
- Model backtest summary
- Strategy Lab backtest
- Intraday scanner
