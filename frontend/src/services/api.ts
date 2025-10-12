import axios, { AxiosInstance, AxiosResponse, AxiosError } from 'axios';
import { toast } from 'react-hot-toast';
import { environmentService, type ConnectionTestResult } from './environment';

interface ApiResponse<T> {
  data: T;
  status: number;
}

export interface EngineScenarioConfig {
  key: string;
  params?: Record<string, unknown>;
  repetitions?: number;
}

export interface EngineRunnerConfig {
  key: string;
  config?: Record<string, unknown>;
}

export interface EngineConfig {
  scenarios: EngineScenarioConfig[];
  runners: EngineRunnerConfig[];
  metrics?: string[];
  validators?: string[];
  parallelism?: number;
}

export interface EngineReportTotals {
  runs: number;
  success: number;
  failed: number;
}

export interface EngineReport {
  status?: string;
  totals?: EngineReportTotals;
  details?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

class ApiService {
  private api: AxiosInstance;
  private ws: WebSocket | null = null;

  constructor() {
    const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    this.api = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 10000,
    });

    this.api.interceptors.response.use(
      (response: AxiosResponse) => response,
      (error: AxiosError) => {
        const url = error.config?.url;
        if (url && (url.includes('get_preferences') || url.includes('set_preferences'))) {
          console.error('Preferences API Error Details:', {
            status: error.response?.status,
            statusText: error.response?.statusText,
            url: url,
            method: error.config?.method,
            data: error.config?.data,
            headers: error.config?.headers,
            responseData: error.response?.data
          });
        }
        if (error.response?.status === 401) {
          toast.error('Session expired. Please refresh the page.');
        } else if ((error.response?.status ?? 0) >= 500) {
          toast.error('Server error. Please try again later.');
        }
        return Promise.reject(error);
      }
    );
  }

  async get<T>(endpoint: string, params?: Record<string, unknown>): Promise<ApiResponse<T>> {
    try {
      const response: AxiosResponse<T> = await this.api.get(endpoint, { params });
      return { data: response.data, status: response.status };
    } catch (error: unknown) {
      const axiosError = error as AxiosError;
      console.error("API call failed:", {
        url: axiosError.config?.url,
        code: axiosError.code,
        message: axiosError.message,
        stack: axiosError.stack,
      });
      toast.error(`API request failed: ${axiosError.message}`);
      throw axiosError;
    }
  }

  async post<T>(endpoint: string, data?: Record<string, unknown>, config?: Record<string, unknown>): Promise<ApiResponse<T>> {
    try {
      const response: AxiosResponse<T> = await this.api.post(endpoint, data, config);
      return { data: response.data, status: response.status };
    } catch (error: unknown) {
      const axiosError = error as AxiosError;
      console.error("API call failed:", {
        url: axiosError.config?.url,
        code: axiosError.code,
        message: axiosError.message,
        stack: axiosError.stack,
      });
      toast.error(`API request failed: ${axiosError.message}`);
      throw axiosError;
    }
  }

  async put<T>(endpoint: string, data?: Record<string, unknown>, config?: Record<string, unknown>): Promise<ApiResponse<T>> {
    try {
      const response: AxiosResponse<T> = await this.api.put(endpoint, data, config);
      return { data: response.data, status: response.status };
    } catch (error: unknown) {
      const axiosError = error as AxiosError;
      console.error("API call failed:", {
        url: axiosError.config?.url,
        code: axiosError.code,
        message: axiosError.message,
        stack: axiosError.stack,
      });
      toast.error(`API request failed: ${axiosError.message}`);
      throw axiosError;
    }
  }

  async delete<T>(endpoint: string, config?: Record<string, unknown>): Promise<ApiResponse<T>> {
    try {
      const response: AxiosResponse<T> = await this.api.delete(endpoint, config);
      return { data: response.data, status: response.status };
    } catch (error: unknown) {
      const axiosError = error as AxiosError;
      console.error("API call failed:", {
        url: axiosError.config?.url,
        code: axiosError.code,
        message: axiosError.message,
        stack: axiosError.stack,
      });
      toast.error(`API request failed: ${axiosError.message}`);
      throw axiosError;
    }
  }

  async checkHealth(): Promise<ApiResponse<{ status: string }>> {
    try {
      const res = await this.get<{ status: string }>('/health');
      return res;
    } catch (error: unknown) {
      const err = error as AxiosError;
      if (err.response?.status === 503) {
        console.error("Backend unavailable, retrying in 5s");
        // Optional: implement retry logic here, e.g., setTimeout and recurse
        toast.error('Backend starting up... Please wait.');
      }
      throw error;
    }
  }

  async getClearMLStatus(): Promise<ApiResponse<{ connected: boolean }>> {
    // Backend exposes ClearML stack status under /api/v1/stack/clearml/status
    return this.get('/api/v1/stack/clearml/status');
  }

  async getExperiments(project?: string): Promise<ApiResponse<Experiment[]>> {
    const params = project ? { project } : {};
    try {
      const res = await this.get<unknown>('/api/v1/experiments', params);
      const normalized = this.normalizeExperiments(res.data);
      const mapped = normalized.map((e) => this.toFrontendExperiment(e));
      return { data: mapped, status: res.status };
    } catch (error) {
      console.error('Experiments API Error:', error);
      throw error;
    }
  }

  private normalizeExperiments(input: unknown): Experiment[] {
    if (Array.isArray(input)) return input as Experiment[];
    if (typeof input === 'string') {
      try {
        return this.normalizeExperiments(JSON.parse(input));
      } catch {
        return [];
      }
    }
    if (input && typeof input === 'object') {
      const obj = input as Record<string, unknown>;

      const items = obj['items'];
      if (Array.isArray(items)) return items as Experiment[];

      const experiments = obj['experiments'];
      if (Array.isArray(experiments)) return experiments as Experiment[];

      const data = obj['data'];
      if (Array.isArray(data)) return data as Experiment[];

      // Keyed map of experiments { [id]: Experiment }
      const values = Object.values(obj);
      if (values.length > 0 && values.every((v) => v && typeof v === 'object')) {
        return values as Experiment[];
      }
      return [];
    }
    return [];
  }

  private toFrontendExperiment(input: unknown): Experiment {
    const obj = (input && typeof input === 'object' ? (input as Record<string, unknown>) : {}) as Record<string, unknown>;

    const statusRaw = String(obj['status'] ?? '');
    const statusMap: Record<string, Experiment['status']> = {
      draft: 'queued',
      queued: 'queued',
      running: 'running',
      completed: 'completed',
      failed: 'failed',
    };
    const status: Experiment['status'] = statusMap[statusRaw] ?? 'queued';

    const createdVal = obj['created'] ?? obj['created_at'];
    const updatedVal = obj['updated'] ?? obj['updated_at'];
    const created = typeof createdVal === 'string' ? createdVal : new Date().toISOString();
    const updated = typeof updatedVal === 'string' ? updatedVal : created;

    const tags = Array.isArray(obj['tags']) ? (obj['tags'] as string[]) : [];
    const progress = typeof obj['progress'] === 'number' ? (obj['progress'] as number) : undefined;

    const metricsSrc = obj['metrics'];
    let metrics: Experiment['metrics'] | undefined = undefined;
    if (metricsSrc && typeof metricsSrc === 'object') {
      const m = metricsSrc as Record<string, unknown>;
      metrics = {
        profit: typeof m['profit'] === 'number' ? (m['profit'] as number) : undefined,
        marketShare: typeof m['marketShare'] === 'number' ? (m['marketShare'] as number) : undefined,
        satisfaction: typeof m['satisfaction'] === 'number' ? (m['satisfaction'] as number) : undefined,
        score: typeof m['score'] === 'number' ? (m['score'] as number) : undefined,
      };
    }

    return {
      id: String(obj['id'] ?? ''),
      name: String(obj['name'] ?? 'Untitled'),
      status,
      metrics,
      progress,
      tags,
      created,
      updated,
    };
  }

  async createExperiment(experiment: ExperimentCreateData): Promise<ApiResponse<Experiment>> {
    // Map frontend fields to backend ExperimentCreate model:
    // backend expects: { name, description?, agent_id, scenario_id, params }
    const payload = {
      name: experiment.name,
      description: experiment.description ?? undefined,
      agent_id: experiment.agent_id ?? 'agent-default',
      scenario_id: experiment.scenario,
      params: {
        ...experiment.config.adjustments,
        game_mode: experiment.config.gameMode,
        with_server: experiment.config.withServer,
      },
    };
    return this.post('/api/v1/experiments', payload as unknown as Record<string, unknown>);
  }

  async runBenchmark(config: EngineConfig): Promise<EngineReport> {
    try {
      const response: AxiosResponse<EngineReport> = await this.api.post(
        '/protected/run-benchmark',
        config,
      );
      return response.data;
    } catch (error: unknown) {
      const axiosError = error as AxiosError;
      console.error('Benchmark execution failed:', {
        url: axiosError.config?.url,
        code: axiosError.code,
        message: axiosError.message,
        response: axiosError.response?.data,
      });
      toast.error('Benchmark run failed');
      throw axiosError;
    }
  }

  async cloneExperiment(id: string, name: string): Promise<ApiResponse<Experiment>> {
    // Backend does not expose a clone route currently; keep path aligned in case it exists later.
    return this.post(`/api/v1/experiments/${id}/clone`, { name });
  }

  async stopExperiment(id: string): Promise<ApiResponse<Experiment>> {
    return this.post(`/api/v1/experiments/${id}/stop`);
  }

  async getLeaderboard(limit?: number): Promise<ApiResponse<LeaderboardEntry[]>> {
    const params = limit ? { limit } : {};
    return this.get('/api/v1/leaderboard', params);
  }

  async getSystemStats(): Promise<ApiResponse<SystemStats>> {
    return this.get('/system/stats');
  }

  async startClearMLStack(): Promise<ApiResponse<{ success: boolean }>> {
    // Use backend stack control route (enabled only when ALLOW_STACK_CONTROL=true)
    return this.post('/api/v1/stack/clearml/start', {});
  }

  async stopClearMLStack(): Promise<ApiResponse<{ success?: boolean; stopped?: boolean; message?: string }>> {
    // Stop the ClearML stack via backend route
    return this.post('/api/v1/stack/clearml/stop', {});
  }

  async checkEnvConfiguration(): Promise<ApiResponse<EnvCheckResponse>> {
    return this.get('/setup/env-check');
  }

  async updateConfiguration(config: ConfigUpdateRequest): Promise<ApiResponse<ConfigUpdateResponse>> {
    return this.post('/setup/update-config', config as unknown as Record<string, unknown>);
  }
  
  async getMedusaLogs(): Promise<string> {
    const response = await this.api.get('/api/v1/medusa/logs', { responseType: 'text' });
    return response.data;
  }

  // WebSocket methods
  connectWebSocket(onMessage: (data: WebSocketMessage) => void, onError?: (error: Event) => void): void {
    try {
      const wsURL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/realtime';
      this.ws = new WebSocket(wsURL);
      
      this.ws.onopen = () => {
        console.log('WebSocket connected');
      };

      this.ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          onMessage(data);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        onError?.(error);
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
      };
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
    }
  }

  disconnectWebSocket(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  subscribe(event: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'subscribe', event }));
    }
  }

  unsubscribe(event: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'unsubscribe', event }));
    }
  }

  // API Key Management Methods
  
  /**
   * Test OpenAI API connection with provided key
   */
  async testOpenAIConnection(apiKey: string): Promise<ConnectionTestResult> {
    try {
      const response = await fetch('https://api.openai.com/v1/models', {
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(10000), // 10 second timeout
      });

      if (response.ok) {
        const data = await response.json();
        return {
          success: true,
          message: `Connected successfully. Found ${data.data?.length || 0} models available.`
        };
      } else if (response.status === 401) {
        return { success: false, message: 'Invalid API key. Please check your OpenAI API key.' };
      } else if (response.status === 429) {
        return { success: false, message: 'Rate limit exceeded. Please try again later.' };
      } else {
        return { success: false, message: `API error: ${response.status} ${response.statusText}` };
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return { success: false, message: 'Connection timeout' };
      }
      return {
        success: false,
        message: 'Connection failed',
        details: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  /**
   * Test OpenRouter API connection with provided key
   */
  async testOpenRouterConnection(apiKey: string): Promise<ConnectionTestResult> {
    // Debug log: Check key format without exposing full key
    console.log('OpenRouter test: Key prefix/format check', {
      startsWithSkOr: apiKey.startsWith('sk-or-'),
      length: apiKey.length,
      hasWhitespace: /\s/.test(apiKey)
    });

    try {
      const requestHeaders = {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      };
      // Debug log: Request details (headers keys only)
      console.log('OpenRouter test: Request', {
        url: 'https://openrouter.ai/api/v1/models',
        method: 'GET',
        headersKeys: Object.keys(requestHeaders),
        hasAuthHeader: 'Authorization' in requestHeaders
      });

      const response = await fetch('https://openrouter.ai/api/v1/models', {
        headers: requestHeaders,
        signal: AbortSignal.timeout(10000), // 10 second timeout
      });

      // Debug log: Response details
      console.log('OpenRouter test: Response', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        headers: [...response.headers.entries()]
      });

      if (response.ok) {
        const data = await response.json();
        console.log('OpenRouter test: Success data preview', { modelCount: data.data?.length || 0 });
        return {
          success: true,
          message: `Connected successfully. Found ${data.data?.length || 0} models available.`
        };
      } else {
        // Log full error body on non-OK
        const errorBody = await response.text();
        console.log('OpenRouter test: Error body', errorBody);
        if (response.status === 401) {
          return { success: false, message: `401 Unauthorized. Details: ${errorBody || 'Check key/credits.'}` };
        } else if (response.status === 429) {
          return { success: false, message: 'Rate limit exceeded. Please try again later.' };
        } else {
          return { success: false, message: `API error: ${response.status} ${response.statusText}. Body: ${errorBody}` };
        }
      }
    } catch (error) {
      console.error('OpenRouter test: Exception', error);
      if (error instanceof Error && error.name === 'AbortError') {
        return { success: false, message: 'Connection timeout' };
      }
      return {
        success: false,
        message: 'Connection failed',
        details: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  /**
   * Test ClearML connection with provided credentials
   */
  async testClearMLConnection(accessKey: string, secretKey: string): Promise<ConnectionTestResult> {
    try {
      const apiHost = 'http://localhost:8008';
      
      // Try to authenticate with ClearML API
      const credentials = btoa(`${accessKey}:${secretKey}`);
      const response = await fetch(`${apiHost}/auth.login`, {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${credentials}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          access_key: accessKey,
          secret_key: secretKey,
        }),
        signal: AbortSignal.timeout(10000), // 10 second timeout
      });

      if (response.ok) {
        return { success: true, message: 'ClearML connection successful' };
      } else if (response.status === 401) {
        return { success: false, message: 'Invalid credentials. Please check your access and secret keys.' };
      } else {
        return { success: false, message: `ClearML API error: ${response.status} ${response.statusText}` };
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return { success: false, message: 'Connection timeout' };
      }
      // If we can't reach the server, provide helpful guidance
      return {
        success: false,
        message: 'ClearML server not reachable',
        details: 'Make sure ClearML server is running on localhost:8008. You can start it from the Settings page.'
      };
    }
  }

  /**
   * Get all stored API keys from environment service
   */
  getStoredApiKeys() {
    return environmentService.getStoredApiKeys();
  }

  /**
   * Set API key for a specific service
   */
  setApiKey(service: 'OPENAI_API_KEY' | 'OPENROUTER_API_KEY' | 'CLEARML_ACCESS_KEY' | 'CLEARML_SECRET_KEY', key: string): void {
    environmentService.setApiKey(service, key);
  }

  /**
   * Clear all stored API keys
   */
  clearApiKeys(): void {
    environmentService.clearApiKeys();
  }

  /**
   * Get environment status overview
   */
  getEnvironmentStatus() {
    return {
      services: environmentService.getServiceStatuses(),
      basicSetupComplete: environmentService.isBasicSetupComplete(),
      missingKeys: environmentService.getMissingCriticalKeys(),
    };
  }

  /**
   * Test all configured API connections
   */
  async testAllConnections(): Promise<Record<string, ConnectionTestResult>> {
    const config = environmentService.getStoredApiKeys();
    const results: Record<string, ConnectionTestResult> = {};

    // Test each configured service
    if (config.openaiApiKey) {
      results.openai = await this.testOpenAIConnection(config.openaiApiKey);
    }
    
    if (config.openrouterApiKey) {
      results.openrouter = await this.testOpenRouterConnection(config.openrouterApiKey);
    }
    
    if (config.clearmlAccessKey && config.clearmlSecretKey) {
      results.clearml = await this.testClearMLConnection(config.clearmlAccessKey, config.clearmlSecretKey);
    }

    return results;
  }
}

// Type definitions for better type safety
interface Experiment {
  id: string;
  name: string;
  status: 'running' | 'completed' | 'failed' | 'queued';
  metrics?: {
    profit?: number;
    marketShare?: number;
    satisfaction?: number;
    score?: number;
  };
  progress?: number;
  tags?: string[];
  created: string;
  updated: string;
}

interface ExperimentCreateData {
  name: string;
  scenario: string;
  config: {
    gameMode?: boolean;
    withServer?: boolean;
    adjustments?: Record<string, unknown>;
  };
  description?: string;
  agent_id?: string;
}

interface SystemStats {
  experiments: {
    total: number;
    running: number;
    completed: number;
    failed: number;
  };
  performance: {
    avgScore: number;
    topScore: number;
    successRate: number;
  };
  resources: {
    cpuUsage: number;
    memoryUsage: number;
    activeWorkers: number;
  };
}

interface WebSocketMessage {
  type: string;
  data: unknown;
}

interface EnvCheckResponse {
  exists: boolean;
  valid: boolean;
  missing_keys: string[];
  required_keys: string[];
  environment?: string;
  auth_enabled?: boolean;
}

interface ConfigUpdateResponse {
  success: boolean;
  message: string;
  environment: string;
}

interface ConfigUpdateRequest {
  environment: string;
  auth_enabled: boolean;
  cors_origins: string;
  mongo_username: string;
  mongo_password: string;
  redis_password: string;
  clearml_access_key?: string;
  clearml_secret_key?: string;
}

interface LeaderboardEntry {
  rank: number;
  experimentId: string;
  name: string;
  score: number;
  model: string;
  status: string;
  completedAt: string;
  avatar: string;
  badge: 'gold' | 'silver' | 'bronze' | 'default';
}

export const apiService = new ApiService();
export const wsService = apiService;

export type {
  ApiResponse,
  EngineConfig,
  EngineReport,
  EngineRunnerConfig,
  EngineScenarioConfig,
  Experiment,
  ExperimentCreateData,
  SystemStats,
  WebSocketMessage,
  EnvCheckResponse,
  ConfigUpdateResponse,
  ConfigUpdateRequest,
  LeaderboardEntry,
};
