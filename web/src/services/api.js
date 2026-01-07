/**
 * War Games API Service
 * 
 * Connects to the existing FastAPI backend for all data operations.
 * No business logic duplication - the React frontend is purely presentational.
 */

import axios from 'axios'

// API base URL - connects to existing FastAPI backend
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const api = axios.create({
    baseURL: API_BASE,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
})

// Request interceptor for auth
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('wargames_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Response interceptor for error handling
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            // Handle auth error
            localStorage.removeItem('wargames_token')
            window.location.href = '/login'
        }
        return Promise.reject(error)
    }
)

/**
 * War Game Simulations API
 */
export const WarGamesAPI = {
    /**
     * Create a new war game simulation
     */
    createSimulation: async (config) => {
        const response = await api.post('/experiments', {
            name: config.name || 'War Game Simulation',
            description: config.description || 'Adversarial market simulation',
            scenario_id: config.scenarioId || 'complex_marketplace',
            params: {
                num_products: config.catalog?.length || 20,
                num_orders: config.simulationDays * 10,
                enable_adversarial_events: true,
                ...config.adversarialConfig,
            },
        })
        return response.data
    },

    /**
     * Start a simulation run
     */
    startSimulation: async (experimentId) => {
        const response = await api.post(`/experiments/${experimentId}/runs`, {})
        return response.data
    },

    /**
     * Get simulation status
     */
    getSimulationStatus: async (experimentId, runId) => {
        const response = await api.get(`/experiments/${experimentId}/runs/${runId}/progress`)
        return response.data
    },

    /**
     * Get simulation results
     */
    getResults: async (experimentId) => {
        const response = await api.get(`/experiments/${experimentId}/results`)
        return response.data
    },

    /**
     * Stop a running simulation
     */
    stopSimulation: async (experimentId) => {
        const response = await api.post(`/experiments/${experimentId}/stop`)
        return response.data
    },

    /**
     * List all simulations
     */
    listSimulations: async (page = 1, limit = 20) => {
        const response = await api.get('/experiments', { params: { page, limit } })
        return response.data
    },

    /**
     * Delete a simulation
     */
    deleteSimulation: async (experimentId) => {
        const response = await api.delete(`/experiments/${experimentId}`)
        return response.data
    },
}

/**
 * Catalog Management API
 */
export const CatalogAPI = {
    /**
     * Get product catalog
     */
    getProducts: async () => {
        const response = await api.get('/catalog/products')
        return response.data
    },

    /**
     * Add a product
     */
    addProduct: async (product) => {
        const response = await api.post('/catalog/products', product)
        return response.data
    },

    /**
     * Update a product
     */
    updateProduct: async (sku, updates) => {
        const response = await api.put(`/catalog/products/${sku}`, updates)
        return response.data
    },

    /**
     * Delete a product
     */
    deleteProduct: async (sku) => {
        const response = await api.delete(`/catalog/products/${sku}`)
        return response.data
    },

    /**
     * Import catalog from CSV
     */
    importCSV: async (file) => {
        const formData = new FormData()
        formData.append('file', file)
        const response = await api.post('/catalog/import', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
        return response.data
    },

    /**
     * Export catalog to CSV
     */
    exportCSV: async () => {
        const response = await api.get('/catalog/export', { responseType: 'blob' })
        return response.data
    },
}

/**
 * Scenarios API
 */
export const ScenariosAPI = {
    /**
     * Get available scenario tiers
     */
    getTiers: async () => {
        const response = await api.get('/scenarios/tiers')
        return response.data
    },

    /**
     * Get adversarial event types
     */
    getAdversarialEvents: async () => {
        const response = await api.get('/scenarios/adversarial-events')
        return response.data
    },

    /**
     * Validate scenario configuration
     */
    validateConfig: async (config) => {
        const response = await api.post('/scenarios/validate', config)
        return response.data
    },
}

/**
 * Metrics API (for results)
 */
export const MetricsAPI = {
    /**
     * Get financial metrics for a simulation
     */
    getFinancialMetrics: async (experimentId) => {
        const response = await api.get(`/experiments/${experimentId}/metrics/financial`)
        return response.data
    },

    /**
     * Get adversarial resilience metrics
     */
    getResilienceMetrics: async (experimentId) => {
        const response = await api.get(`/experiments/${experimentId}/metrics/resilience`)
        return response.data
    },

    /**
     * Get tick-by-tick data (for charts)
     */
    getTickData: async (experimentId, fromTick = 0, toTick = null) => {
        const params = { from_tick: fromTick }
        if (toTick) params.to_tick = toTick
        const response = await api.get(`/experiments/${experimentId}/ticks`, { params })
        return response.data
    },

    /**
     * Export results report
     */
    exportReport: async (experimentId, format = 'pdf') => {
        const response = await api.get(`/experiments/${experimentId}/report`, {
            params: { format },
            responseType: 'blob',
        })
        return response.data
    },
}

/**
 * WebSocket for real-time simulation updates
 */
export class SimulationWebSocket {
    constructor(experimentId, runId) {
        this.experimentId = experimentId
        this.runId = runId
        this.ws = null
        this.listeners = new Map()
    }

    connect() {
        const wsUrl = (import.meta.env.VITE_WS_URL || 'ws://localhost:8000') +
            `/api/v1/realtime?simulation_id=${this.experimentId}&run_id=${this.runId}`

        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
            console.log('[WS] Connected to simulation')
            this.emit('connected', {})

            // Subscribe to simulation events
            this.send({
                type: 'subscribe',
                topics: ['simulation_tick', 'simulation_event', 'simulation_complete']
            })
        }

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            this.emit(data.type, data.payload)
        }

        this.ws.onerror = (error) => {
            console.error('[WS] Error:', error)
            this.emit('error', error)
        }

        this.ws.onclose = () => {
            console.log('[WS] Disconnected')
            this.emit('disconnected', {})
        }
    }

    send(message) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message))
        }
    }

    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, [])
        }
        this.listeners.get(event).push(callback)
    }

    off(event, callback) {
        if (this.listeners.has(event)) {
            const callbacks = this.listeners.get(event)
            const index = callbacks.indexOf(callback)
            if (index > -1) {
                callbacks.splice(index, 1)
            }
        }
    }

    emit(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => callback(data))
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close()
            this.ws = null
        }
    }
}

export default api
