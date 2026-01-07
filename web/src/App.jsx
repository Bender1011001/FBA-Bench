import { useState, useEffect, useCallback } from 'react'
import {
  Play,
  Upload,
  Settings,
  BarChart3,
  Shield,
  Zap,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Package,
  DollarSign,
  Target,
  Clock,
  CheckCircle,
  XCircle,
  ChevronRight,
  Plus,
  Trash2,
  Eye,
  Download,
  RefreshCw,
  Swords,
  Trophy,
  Flame,
  SkullIcon
} from 'lucide-react'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts'
import './App.css'

// Demo data for visualization
const generateDemoResults = (adversarialLevel) => {
  const ticks = 180
  const data = []
  let profit = 25000
  let inventory = 500

  for (let i = 0; i < ticks; i++) {
    // Apply adversarial events impact
    const eventImpact = Math.random() < adversarialLevel * 0.01 ? -500 - Math.random() * 1000 : 0
    const dailyProfit = 50 + Math.random() * 150 - (adversarialLevel * 10) + eventImpact
    profit += dailyProfit
    inventory = Math.max(50, inventory + Math.floor(Math.random() * 20) - 10)

    data.push({
      tick: i + 1,
      profit: Math.round(profit),
      inventory,
      revenue: Math.round(200 + Math.random() * 300),
      marketShare: Math.round((15 + Math.random() * 10 - adversarialLevel * 0.5) * 10) / 10
    })
  }

  return data
}

const COLORS = ['#6366f1', '#10b981', '#f97316', '#f43f5e', '#06b6d4', '#8b5cf6']

const adversarialEvents = [
  { id: 'supply_shock', name: 'Supply Chain Shocks', icon: Package, description: 'Port strikes, factory fires, logistics breakdowns', enabled: true, severity: 40 },
  { id: 'price_war', name: 'Competitor Price Wars', icon: Swords, description: 'Aggressive competitors undercutting by 15-20%', enabled: true, severity: 60 },
  { id: 'demand_shock', name: 'Demand Volatility', icon: TrendingDown, description: 'Viral trends, sudden crashes, seasonal spikes', enabled: true, severity: 50 },
  { id: 'fee_hike', name: 'Platform Fee Increases', icon: DollarSign, description: 'Referral, storage, fulfillment fee hikes', enabled: false, severity: 30 },
  { id: 'review_bomb', name: 'Review Bombing', icon: Flame, description: 'Coordinated negative review attacks', enabled: false, severity: 45 },
  { id: 'compliance_trap', name: 'Compliance Traps', icon: AlertTriangle, description: 'Fake policy alerts testing agent skepticism', enabled: true, severity: 80 },
  { id: 'false_intel', name: 'Market Manipulation', icon: Eye, description: 'Deceptive market intelligence', enabled: false, severity: 70 }
]

const demoCatalog = [
  { sku: 'P0001', name: 'Wireless Bluetooth Headphones', price: 79.99, stock: 245, category: 'Electronics', margin: 32 },
  { sku: 'P0002', name: 'Yoga Mat Premium', price: 34.99, stock: 180, category: 'Sports', margin: 45 },
  { sku: 'P0003', name: 'Stainless Steel Water Bottle', price: 24.99, stock: 320, category: 'Home', margin: 55 },
  { sku: 'P0004', name: 'LED Desk Lamp', price: 49.99, stock: 95, category: 'Electronics', margin: 38 },
  { sku: 'P0005', name: 'Organic Coffee Beans 2lb', price: 28.99, stock: 450, category: 'Grocery', margin: 28 },
]

function App() {
  const [currentView, setCurrentView] = useState('dashboard')
  const [catalog, setCatalog] = useState(demoCatalog)
  const [events, setEvents] = useState(adversarialEvents)
  const [simulationRunning, setSimulationRunning] = useState(false)
  const [simulationProgress, setSimulationProgress] = useState(0)
  const [simulationResults, setSimulationResults] = useState(null)
  const [scenarioTier, setScenarioTier] = useState(2)
  const [simulationDays, setSimulationDays] = useState(180)

  // Calculate total adversarial severity
  const totalSeverity = events.filter(e => e.enabled).reduce((sum, e) => sum + e.severity, 0)
  const averageSeverity = events.filter(e => e.enabled).length > 0
    ? Math.round(totalSeverity / events.filter(e => e.enabled).length)
    : 0

  // Simulate war game
  const runWarGame = useCallback(() => {
    setSimulationRunning(true)
    setSimulationProgress(0)
    setSimulationResults(null)
    setCurrentView('simulation')

    // Simulate progress
    const interval = setInterval(() => {
      setSimulationProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval)
          setSimulationRunning(false)
          setSimulationResults(generateDemoResults(averageSeverity))
          return 100
        }
        return prev + 2
      })
    }, 100)
  }, [averageSeverity])

  const toggleEvent = (eventId) => {
    setEvents(events.map(e =>
      e.id === eventId ? { ...e, enabled: !e.enabled } : e
    ))
  }

  const updateEventSeverity = (eventId, severity) => {
    setEvents(events.map(e =>
      e.id === eventId ? { ...e, severity: parseInt(severity) } : e
    ))
  }

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <Swords size={28} className="logo-icon" />
            <span className="logo-text">War Games</span>
          </div>
          <span className="version-badge">Enterprise</span>
        </div>

        <nav className="sidebar-nav">
          <button
            className={`nav-item ${currentView === 'dashboard' ? 'active' : ''}`}
            onClick={() => setCurrentView('dashboard')}
          >
            <BarChart3 size={20} />
            <span>Dashboard</span>
          </button>
          <button
            className={`nav-item ${currentView === 'catalog' ? 'active' : ''}`}
            onClick={() => setCurrentView('catalog')}
          >
            <Package size={20} />
            <span>Product Catalog</span>
          </button>
          <button
            className={`nav-item ${currentView === 'scenarios' ? 'active' : ''}`}
            onClick={() => setCurrentView('scenarios')}
          >
            <Shield size={20} />
            <span>Adversarial Events</span>
          </button>
          <button
            className={`nav-item ${currentView === 'simulation' ? 'active' : ''}`}
            onClick={() => setCurrentView('simulation')}
          >
            <Play size={20} />
            <span>Run Simulation</span>
          </button>
          <button
            className={`nav-item ${currentView === 'results' ? 'active' : ''}`}
            onClick={() => setCurrentView('results')}
          >
            <Trophy size={20} />
            <span>Results</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="threat-level">
            <div className="threat-header">
              <AlertTriangle size={16} />
              <span>Threat Level</span>
            </div>
            <div className="threat-meter">
              <div
                className="threat-fill"
                style={{
                  width: `${averageSeverity}%`,
                  background: averageSeverity > 60 ? 'var(--gradient-fire)' : 'var(--gradient-primary)'
                }}
              />
            </div>
            <span className="threat-value">{averageSeverity}% Severity</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {/* Header */}
        <header className="main-header">
          <div className="header-left">
            <h1>{currentView === 'dashboard' && 'War Games Dashboard'}
              {currentView === 'catalog' && 'Product Catalog'}
              {currentView === 'scenarios' && 'Adversarial Events'}
              {currentView === 'simulation' && 'Run War Game'}
              {currentView === 'results' && 'Simulation Results'}</h1>
            <p className="header-subtitle">
              {currentView === 'dashboard' && 'Test your business resilience against market chaos'}
              {currentView === 'catalog' && 'Manage products to include in your simulation'}
              {currentView === 'scenarios' && 'Configure adversarial market events'}
              {currentView === 'simulation' && 'Execute war game simulation'}
              {currentView === 'results' && 'Analyze simulation outcomes'}
            </p>
          </div>
          <div className="header-right">
            <button className="btn btn-primary btn-lg" onClick={runWarGame}>
              <Play size={20} />
              Launch War Game
            </button>
          </div>
        </header>

        {/* Content Area */}
        <div className="content-area">
          {/* Dashboard View */}
          {currentView === 'dashboard' && (
            <div className="dashboard slide-in">
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-icon" style={{ background: 'rgba(99, 102, 241, 0.15)' }}>
                    <Package size={24} style={{ color: 'var(--primary)' }} />
                  </div>
                  <div className="stat-content">
                    <span className="stat-label">Products</span>
                    <span className="stat-value">{catalog.length}</span>
                    <span className="stat-change positive">
                      <TrendingUp size={14} /> Ready for testing
                    </span>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon" style={{ background: 'rgba(249, 115, 22, 0.15)' }}>
                    <Zap size={24} style={{ color: 'var(--accent-orange)' }} />
                  </div>
                  <div className="stat-content">
                    <span className="stat-label">Active Threats</span>
                    <span className="stat-value">{events.filter(e => e.enabled).length}</span>
                    <span className="stat-change negative">
                      <AlertTriangle size={14} /> of {events.length} configured
                    </span>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon" style={{ background: 'rgba(16, 185, 129, 0.15)' }}>
                    <DollarSign size={24} style={{ color: 'var(--accent-emerald)' }} />
                  </div>
                  <div className="stat-content">
                    <span className="stat-label">Catalog Value</span>
                    <span className="stat-value">${catalog.reduce((sum, p) => sum + p.price * p.stock, 0).toLocaleString()}</span>
                    <span className="stat-change positive">
                      <TrendingUp size={14} /> Total inventory value
                    </span>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon" style={{ background: 'rgba(244, 63, 94, 0.15)' }}>
                    <Target size={24} style={{ color: 'var(--accent-rose)' }} />
                  </div>
                  <div className="stat-content">
                    <span className="stat-label">Scenario Tier</span>
                    <span className="stat-value">Tier {scenarioTier}</span>
                    <span className="stat-change">
                      {scenarioTier === 0 && 'Baseline'}
                      {scenarioTier === 1 && 'Moderate'}
                      {scenarioTier === 2 && 'Advanced'}
                      {scenarioTier === 3 && 'Expert'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="dashboard-grid">
                <div className="card">
                  <div className="card-header">
                    <h3 className="card-title">Quick Start Guide</h3>
                  </div>
                  <div className="quick-start">
                    <div className="step">
                      <div className="step-number">1</div>
                      <div className="step-content">
                        <h4>Upload Your Catalog</h4>
                        <p>Import your product data via CSV or connect to Amazon Seller Central</p>
                      </div>
                      <ChevronRight size={20} className="step-arrow" />
                    </div>
                    <div className="step">
                      <div className="step-number">2</div>
                      <div className="step-content">
                        <h4>Configure Threats</h4>
                        <p>Select adversarial events: price wars, supply shocks, review bombing</p>
                      </div>
                      <ChevronRight size={20} className="step-arrow" />
                    </div>
                    <div className="step">
                      <div className="step-number">3</div>
                      <div className="step-content">
                        <h4>Launch War Game</h4>
                        <p>Run simulation and see how your business survives chaos</p>
                      </div>
                      <CheckCircle size={20} className="step-check" />
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="card-header">
                    <h3 className="card-title">Threat Overview</h3>
                  </div>
                  <div className="threat-overview">
                    {events.filter(e => e.enabled).map(event => (
                      <div key={event.id} className="threat-item">
                        <event.icon size={18} />
                        <span className="threat-name">{event.name}</span>
                        <div className="threat-bar">
                          <div
                            className="threat-bar-fill"
                            style={{
                              width: `${event.severity}%`,
                              background: event.severity > 60 ? 'var(--accent-rose)' : 'var(--accent-orange)'
                            }}
                          />
                        </div>
                        <span className="threat-percent">{event.severity}%</span>
                      </div>
                    ))}
                    {events.filter(e => e.enabled).length === 0 && (
                      <p className="text-muted text-center">No threats configured</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Catalog View */}
          {currentView === 'catalog' && (
            <div className="catalog-view slide-in">
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Your Products ({catalog.length})</h3>
                  <div className="flex gap-2">
                    <button className="btn btn-secondary">
                      <Upload size={18} />
                      Import CSV
                    </button>
                    <button className="btn btn-primary">
                      <Plus size={18} />
                      Add Product
                    </button>
                  </div>
                </div>
                <div className="table-container">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>SKU</th>
                        <th>Product Name</th>
                        <th>Category</th>
                        <th>Price</th>
                        <th>Stock</th>
                        <th>Margin</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {catalog.map(product => (
                        <tr key={product.sku}>
                          <td><code>{product.sku}</code></td>
                          <td>{product.name}</td>
                          <td><span className="badge badge-info">{product.category}</span></td>
                          <td>${product.price.toFixed(2)}</td>
                          <td>{product.stock}</td>
                          <td>
                            <span className={`badge ${product.margin > 40 ? 'badge-success' : product.margin > 25 ? 'badge-warning' : 'badge-danger'}`}>
                              {product.margin}%
                            </span>
                          </td>
                          <td>
                            <div className="flex gap-1">
                              <button className="btn btn-icon btn-secondary"><Eye size={16} /></button>
                              <button className="btn btn-icon btn-secondary"><Trash2 size={16} /></button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Scenarios View */}
          {currentView === 'scenarios' && (
            <div className="scenarios-view slide-in">
              <div className="scenarios-header">
                <div className="scenario-tier-selector">
                  <label className="input-label">Scenario Difficulty Tier</label>
                  <div className="tier-buttons">
                    {[0, 1, 2, 3].map(tier => (
                      <button
                        key={tier}
                        className={`tier-btn ${scenarioTier === tier ? 'active' : ''}`}
                        onClick={() => setScenarioTier(tier)}
                      >
                        <span className="tier-number">Tier {tier}</span>
                        <span className="tier-label">
                          {tier === 0 && 'Baseline'}
                          {tier === 1 && 'Moderate'}
                          {tier === 2 && 'Advanced'}
                          {tier === 3 && 'Expert'}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="simulation-duration">
                  <label className="input-label">Simulation Duration</label>
                  <div className="duration-input">
                    <input
                      type="number"
                      className="input"
                      value={simulationDays}
                      onChange={(e) => setSimulationDays(parseInt(e.target.value))}
                      min={30}
                      max={365}
                    />
                    <span className="duration-suffix">days</span>
                  </div>
                </div>
              </div>

              <div className="events-grid">
                {events.map(event => (
                  <div key={event.id} className={`event-card ${event.enabled ? 'enabled' : ''}`}>
                    <div className="event-header">
                      <div className="event-icon-wrap">
                        <event.icon size={24} />
                      </div>
                      <div className="event-toggle">
                        <label className="switch">
                          <input
                            type="checkbox"
                            checked={event.enabled}
                            onChange={() => toggleEvent(event.id)}
                          />
                          <span className="slider"></span>
                        </label>
                      </div>
                    </div>
                    <h3 className="event-name">{event.name}</h3>
                    <p className="event-description">{event.description}</p>
                    <div className="event-severity">
                      <div className="severity-header">
                        <span>Severity</span>
                        <span className="severity-value">{event.severity}%</span>
                      </div>
                      <input
                        type="range"
                        className="range"
                        min="10"
                        max="100"
                        value={event.severity}
                        onChange={(e) => updateEventSeverity(event.id, e.target.value)}
                        disabled={!event.enabled}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Simulation View */}
          {currentView === 'simulation' && (
            <div className="simulation-view slide-in">
              {simulationRunning ? (
                <div className="simulation-running">
                  <div className="simulation-animation">
                    <div className="pulse-ring"></div>
                    <div className="pulse-ring delay-1"></div>
                    <div className="pulse-ring delay-2"></div>
                    <Swords size={64} className="simulation-icon" />
                  </div>
                  <h2>War Game in Progress</h2>
                  <p className="text-secondary">Simulating {simulationDays} days of market chaos...</p>
                  <div className="simulation-progress">
                    <div className="progress-header">
                      <span>Day {Math.floor(simulationDays * simulationProgress / 100)} of {simulationDays}</span>
                      <span>{simulationProgress}%</span>
                    </div>
                    <div className="progress">
                      <div className="progress-bar" style={{ width: `${simulationProgress}%` }}></div>
                    </div>
                  </div>
                  <div className="simulation-events">
                    {simulationProgress > 20 && <div className="sim-event fade-in">⚡ Supply chain shock applied</div>}
                    {simulationProgress > 40 && <div className="sim-event fade-in">🔥 Competitor price war initiated</div>}
                    {simulationProgress > 60 && <div className="sim-event fade-in">⚠️ Compliance trap triggered</div>}
                    {simulationProgress > 80 && <div className="sim-event fade-in">📊 Calculating final metrics...</div>}
                  </div>
                </div>
              ) : simulationResults ? (
                <div className="simulation-complete">
                  <div className="complete-header">
                    <CheckCircle size={48} className="complete-icon" />
                    <h2>War Game Complete</h2>
                    <p>Your business survived {simulationDays} days of adversarial conditions</p>
                  </div>
                  <button
                    className="btn btn-primary btn-lg"
                    onClick={() => setCurrentView('results')}
                  >
                    <BarChart3 size={20} />
                    View Full Results
                  </button>
                </div>
              ) : (
                <div className="simulation-ready">
                  <div className="ready-card">
                    <Swords size={64} className="ready-icon" />
                    <h2>Ready to Launch</h2>
                    <p className="text-secondary mb-6">
                      Configure your adversarial events and click Launch to start the war game simulation.
                    </p>
                    <div className="ready-stats">
                      <div className="ready-stat">
                        <span className="ready-stat-value">{catalog.length}</span>
                        <span className="ready-stat-label">Products</span>
                      </div>
                      <div className="ready-stat">
                        <span className="ready-stat-value">{events.filter(e => e.enabled).length}</span>
                        <span className="ready-stat-label">Threats</span>
                      </div>
                      <div className="ready-stat">
                        <span className="ready-stat-value">{simulationDays}</span>
                        <span className="ready-stat-label">Days</span>
                      </div>
                      <div className="ready-stat">
                        <span className="ready-stat-value">Tier {scenarioTier}</span>
                        <span className="ready-stat-label">Difficulty</span>
                      </div>
                    </div>
                    <button className="btn btn-danger btn-lg" onClick={runWarGame}>
                      <Play size={20} />
                      Launch War Game
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Results View */}
          {currentView === 'results' && simulationResults && (
            <div className="results-view slide-in">
              <div className="results-header">
                <div className="result-score">
                  <div className="score-ring">
                    <svg viewBox="0 0 100 100">
                      <circle cx="50" cy="50" r="45" fill="none" stroke="var(--bg-tertiary)" strokeWidth="8" />
                      <circle
                        cx="50" cy="50" r="45"
                        fill="none"
                        stroke="url(#scoreGradient)"
                        strokeWidth="8"
                        strokeLinecap="round"
                        strokeDasharray={`${78 * 2.83} ${100 * 2.83}`}
                        transform="rotate(-90 50 50)"
                      />
                      <defs>
                        <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                          <stop offset="0%" stopColor="#6366f1" />
                          <stop offset="100%" stopColor="#10b981" />
                        </linearGradient>
                      </defs>
                    </svg>
                    <div className="score-value">
                      <span className="score-number">78</span>
                      <span className="score-label">Resilience Score</span>
                    </div>
                  </div>
                </div>
                <div className="result-summary">
                  <h2>Simulation Summary</h2>
                  <p>Your business demonstrated <strong>strong resilience</strong> against adversarial market conditions.</p>
                  <div className="summary-badges">
                    <span className="badge badge-success">Survived All Events</span>
                    <span className="badge badge-info">Tier 2 Advanced</span>
                    <span className="badge badge-warning">3 Near-Misses</span>
                  </div>
                </div>
              </div>

              <div className="results-grid">
                <div className="card">
                  <div className="card-header">
                    <h3 className="card-title">Profit Over Time</h3>
                  </div>
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height={300}>
                      <AreaChart data={simulationResults}>
                        <defs>
                          <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                            <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                        <XAxis dataKey="tick" stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} />
                        <YAxis stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} />
                        <Tooltip
                          contentStyle={{
                            background: 'var(--bg-secondary)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '8px'
                          }}
                        />
                        <Area type="monotone" dataKey="profit" stroke="#6366f1" fill="url(#profitGradient)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="card">
                  <div className="card-header">
                    <h3 className="card-title">Market Share</h3>
                  </div>
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart data={simulationResults}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                        <XAxis dataKey="tick" stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} />
                        <YAxis stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} />
                        <Tooltip
                          contentStyle={{
                            background: 'var(--bg-secondary)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '8px'
                          }}
                        />
                        <Line type="monotone" dataKey="marketShare" stroke="#10b981" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Key Metrics</h3>
                  <button className="btn btn-secondary">
                    <Download size={18} />
                    Export Report
                  </button>
                </div>
                <div className="metrics-grid">
                  <div className="metric-item">
                    <span className="metric-label">Final Profit</span>
                    <span className="metric-value positive">${simulationResults[simulationResults.length - 1].profit.toLocaleString()}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Avg. Market Share</span>
                    <span className="metric-value">{(simulationResults.reduce((s, r) => s + r.marketShare, 0) / simulationResults.length).toFixed(1)}%</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Events Survived</span>
                    <span className="metric-value">{events.filter(e => e.enabled).length}/{events.length}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Trap Resistance</span>
                    <span className="metric-value positive">92%</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {currentView === 'results' && !simulationResults && (
            <div className="no-results slide-in">
              <div className="no-results-content">
                <BarChart3 size={64} className="no-results-icon" />
                <h2>No Results Yet</h2>
                <p className="text-secondary">Run a War Game simulation to see your results here.</p>
                <button className="btn btn-primary btn-lg" onClick={runWarGame}>
                  <Play size={20} />
                  Launch War Game
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
