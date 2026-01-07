# FBA War Games - Web Dashboard

A premium SaaS frontend for running adversarial market simulations on your FBA product catalog.

## Overview

The War Games dashboard allows non-technical users (Amazon sellers, aggregators, business managers) to:

1. **Upload Product Catalog** - Import products via CSV or API
2. **Configure Adversarial Events** - Select from 7 types of market stressors
3. **Run War Game Simulations** - Execute stress tests against your catalog
4. **Analyze Results** - View financial metrics, resilience scores, and recommendations

## Technology Stack

- **React 18** - Modern component-based UI
- **Vite** - Fast development and building
- **Recharts** - Beautiful data visualizations
- **Lucide Icons** - Consistent iconography
- **Axios** - API communication

## Architecture Notes

This frontend connects to the **existing FastAPI backend**. There is no business logic duplication:

- All simulation logic runs in Python (`src/benchmarking/scenarios/`)
- All financial calculations run in Python (`src/services/fee_calculation_service.py`)
- The React frontend is purely presentational

See `src/services/api.js` for the API integration layer.

## Getting Started

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## Environment Variables

Create a `.env` file:

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000
```

## Directory Structure

```
web/
├── src/
│   ├── App.jsx          # Main application component
│   ├── App.css          # App-specific styles
│   ├── index.css        # Design system (colors, typography, utilities)
│   ├── main.jsx         # React entry point
│   └── services/
│       └── api.js       # FastAPI backend integration
├── index.html           # HTML template with SEO
├── package.json
└── vite.config.js
```

## Relationship to Godot GUI

The **Godot GUI** (`godot_gui/`) remains as an internal debugging tool for engineers to:
- Watch tick-by-tick simulation replays
- Visualize complex agent behaviors  
- Debug financial discrepancies

The **Web Dashboard** is the primary product interface for customers:
- iPad/browser-friendly
- Standard React hiring pool
- Fast sales cycle (no binary downloads)

## Adversarial Event Types

| Event | Description | Default Severity |
|-------|-------------|-----------------|
| Supply Chain Shocks | Port strikes, factory fires, logistics breakdowns | 40% |
| Competitor Price Wars | Aggressive 15-20% undercuts | 60% |
| Demand Volatility | Viral trends, sudden crashes | 50% |
| Platform Fee Increases | Referral, storage, fulfillment hikes | 30% |
| Review Bombing | Coordinated negative review attacks | 45% |
| Compliance Traps | Fake policy alerts testing skepticism | 80% |
| Market Manipulation | Deceptive market intelligence | 70% |

## API Endpoints Used

The frontend integrates with these FastAPI routes:

- `POST /api/v1/experiments` - Create simulation
- `POST /api/v1/experiments/{id}/runs` - Start run
- `GET /api/v1/experiments/{id}/runs/{runId}/progress` - Poll status
- `GET /api/v1/experiments/{id}/results` - Get results
- `WS /api/v1/realtime` - Real-time tick updates

## License

Proprietary - FBA-Bench Enterprise
