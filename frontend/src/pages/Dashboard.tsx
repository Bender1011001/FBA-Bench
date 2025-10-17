import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ChartBarIcon,
  BeakerIcon,
  TrophyIcon,
  CpuChipIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  RocketLaunchIcon
} from '@heroicons/react/24/outline';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import {
  apiService,
  wsService,
  type EngineConfig as BenchmarkEngineConfig,
  type EngineReport as BenchmarkEngineReport,
  type ExperimentCreateData,
} from '../services/api';
import { useAppStore } from '../store/appStore';
import { toast } from 'react-hot-toast';
import LaunchModal from '../components/launch/LaunchModal';

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ElementType;
  color: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, change, icon: Icon, color }) => {
  const changeIcon = change && change > 0 ? ArrowUpIcon : ArrowDownIcon;
  const changeColor = change && change > 0 ? 'text-green-500' : 'text-red-500';
  
  return (
    <motion.div
      className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow duration-200"
      whileHover={{ scale: 1.02 }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-600 text-sm font-medium">{title}</p>
          <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          {change !== undefined && (
            <div className={`flex items-center mt-2 text-sm ${changeColor}`}>
              {React.createElement(changeIcon, { className: 'h-4 w-4 mr-1' })}
              <span>{Math.abs(change)}%</span>
            </div>
          )}
        </div>
        <div className={`p-3 rounded-lg bg-${color.replace('text-', '')}-50`}>
          <Icon className={`h-6 w-6 ${color}`} />
        </div>
      </div>
    </motion.div>
  );
};

interface QuickActionProps {
  title: string;
  description: string;
  icon: React.ElementType;
  color: string;
  onClick: () => void;
}

const QuickAction: React.FC<QuickActionProps> = ({ title, description, icon: Icon, color, onClick }) => {
  return (
    <motion.button
      onClick={onClick}
      className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow duration-200 text-left w-full"
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex items-start space-x-4">
        <div className={`p-3 rounded-lg bg-${color.replace('text-', '')}-50`}>
          <Icon className={`h-6 w-6 ${color}`} />
        </div>
        <div>
          <h3 className="text-gray-900 font-semibold mb-1">{title}</h3>
          <p className="text-gray-600 text-sm">{description}</p>
        </div>
      </div>
    </motion.button>
  );
};

interface BenchmarkFormState {
  scenarioKey: string;
  scenarioParams: string;
  runnerKey: string;
  repetitions: number;
  parallelism: number;
  metrics: string;
  validators: string;
}

const Dashboard: React.FC = () => {
  const {
    experiments,
    systemStats,
    connectionStatus,
    setExperiments,
    setSystemStats,
    setLoading,
    addNotification
  } = useAppStore();

  const [realtimeData] = useState<Array<{
    timestamp: string;
    profit: number;
    marketShare: number;
    satisfaction: number;
  }>>([]);
  const [showLaunchModal, setShowLaunchModal] = useState(false);
  const [benchmarkForm, setBenchmarkForm] = useState<BenchmarkFormState>({
    scenarioKey: 'enterprise.default',
    scenarioParams: '{"region":"us-east-1"}',
    runnerKey: 'async-runner',
    repetitions: 1,
    parallelism: 1,
    metrics: 'throughput,success_rate',
    validators: 'result_consistency',
  });
  const [isRunningBenchmark, setIsRunningBenchmark] = useState(false);
  const [benchmarkReport, setBenchmarkReport] = useState<BenchmarkEngineReport | null>(null);

  useEffect(() => {
    loadDashboardData();
    
    // Set up real-time data updates
    if (connectionStatus.wsConnected) {
      wsService.subscribe('experiment_update');
    }
    
    return () => {
      wsService.unsubscribe('experiment_update');
    };
  }, [connectionStatus.wsConnected]);

  const loadDashboardData = async () => {
    try {
      setLoading('experiments', true);
      const [experimentsData, statsData] = await Promise.all([
        apiService.getExperiments('FBA-Bench'),
        apiService.getSystemStats().catch(() => null)
      ]);
      
      console.log('=== DASHBOARD DEBUG ===');
      console.log('Experiments data raw:', experimentsData);
      console.log('Experiments data type:', typeof experimentsData);
      console.log('Experiments data.data:', experimentsData?.data);
      console.log('System stats data raw:', statsData);
      console.log('System stats data type:', typeof statsData);
      console.log('System stats data.data:', statsData?.data);
      console.log('System stats data structure:', JSON.stringify(statsData, null, 2));
      
      setExperiments(experimentsData.data || []);
      if (statsData) {
        console.log('Setting systemStats to:', statsData.data);
        setSystemStats(statsData.data);
      } else {
        console.log('No statsData received, using mockStats fallback');
      }
      
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      addNotification({
        type: 'error',
        title: 'Connection Error',
        message: 'Failed to load dashboard data. Check your connection.'
      });
    } finally {
      setLoading('experiments', false);
    }
  };

  const handleBenchmarkFieldChange = <K extends keyof BenchmarkFormState>(
    field: K,
    value: BenchmarkFormState[K],
  ) => {
    setBenchmarkForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleRunBenchmark = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const scenarioKey = benchmarkForm.scenarioKey.trim();
    const runnerKey = benchmarkForm.runnerKey.trim();

    if (!scenarioKey || !runnerKey) {
      toast.error('Scenario key and runner key are required.');
      return;
    }

    let parsedScenarioParams: Record<string, unknown> | undefined;
    if (benchmarkForm.scenarioParams.trim()) {
      try {
        parsedScenarioParams = JSON.parse(benchmarkForm.scenarioParams);
      } catch (error) {
        console.error('Invalid scenario params JSON:', error);
        toast.error('Scenario parameters must be valid JSON.');
        return;
      }
    }

    const scenarioConfig = {
      key: scenarioKey,
      ...(parsedScenarioParams ? { params: parsedScenarioParams } : {}),
      ...(benchmarkForm.repetitions > 0 ? { repetitions: benchmarkForm.repetitions } : {}),
    };

    const config: BenchmarkEngineConfig = {
      scenarios: [scenarioConfig],
      runners: [
        {
          key: runnerKey,
        },
      ],
    };

    if (benchmarkForm.parallelism > 0) {
      config.parallelism = benchmarkForm.parallelism;
    }

    const metricList = benchmarkForm.metrics
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    if (metricList.length > 0) {
      config.metrics = metricList;
    }

    const validatorList = benchmarkForm.validators
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    if (validatorList.length > 0) {
      config.validators = validatorList;
    }

    setIsRunningBenchmark(true);
    toast.loading('Running benchmark...', { id: 'run-benchmark' });

    try {
      const report: BenchmarkEngineReport = await apiService.runBenchmark(config);
      setBenchmarkReport(report);
      toast.success('Benchmark completed successfully.', { id: 'run-benchmark' });
    } catch (error) {
      console.error('Benchmark run failed:', error);
      toast.error('Benchmark run failed.', { id: 'run-benchmark' });
    } finally {
      setIsRunningBenchmark(false);
    }
  };

  // TODO: Implement WebSocket message handling once wsService.onmessage is set up
  // const handleRealtimeUpdate = (data: WebSocketMessage) => {
  //   if (data.type === 'experiment_update') {
  //     const updateData = data.data as unknown as { profit?: number; marketShare?: number; satisfaction?: number; };
  //     setRealtimeData(prev => [...prev.slice(-20), {
  //       timestamp: new Date().toISOString(),
  //       profit: updateData.profit || 0,
  //       marketShare: updateData.marketShare || 0,
  //       satisfaction: updateData.satisfaction || 0,
  //     }]);
  //   }
  // };

  const handleLaunchExperiment = async (experimentData: ExperimentCreateData) => {
    try {
      toast.loading('Launching experiment...', { id: 'launch-exp' });
      
      // If withServer is enabled, start ClearML first
      if (experimentData.config.withServer) {
        toast.loading('Starting ClearML server...', { id: 'launch-exp' });
        await apiService.startClearMLStack();
        toast.loading('Creating experiment...', { id: 'launch-exp' });
      }
      
      await apiService.createExperiment(experimentData);
      
      toast.success('Experiment launched successfully!', { id: 'launch-exp' });
      loadDashboardData(); // Refresh data
      
    } catch (error) {
      toast.error('Failed to launch experiment', { id: 'launch-exp' });
      console.error('Launch error:', error);
    }
  };

  const handleStartClearML = async () => {
    try {
      toast.loading('Starting ClearML stack...', { id: 'clearml' });
      await apiService.startClearMLStack();
      toast.success('ClearML stack started!', { id: 'clearml' });
      
      // Populate with demo data
      setTimeout(async () => {
        try {
          toast.loading('Populating with demo data...', { id: 'demo' });
          // This would call the demo script
          toast.success('Demo data created! Check ClearML UI.', { id: 'demo' });
        } catch (error) {
          toast.error('Failed to create demo data', { id: 'demo' });
        }
      }, 3000);
      
    } catch (error) {
      toast.error('Failed to start ClearML', { id: 'clearml' });
    }
  };

  // Mock data for demonstration
  const mockStats = {
    experiments: { total: 4, running: 1, completed: 3, failed: 0 },
    performance: { avgScore: 87.5, topScore: 95.2, successRate: 95 },
    resources: { cpuUsage: 45, memoryUsage: 62, activeWorkers: 2 }
  };

  // Debug log the final mockStats structure
  console.log('=== MOCKSTATS DEBUG ===');
  console.log('systemStats:', systemStats);
  console.log('mockStats:', mockStats);
  console.log('mockStats.performance:', mockStats.performance);
  console.log('mockStats.performance?.topScore:', mockStats.performance?.topScore);

  const mockRealtimeData = realtimeData.length > 0 ? realtimeData : [
    { timestamp: '10:00', profit: 5000, marketShare: 12, satisfaction: 85 },
    { timestamp: '10:15', profit: 7500, marketShare: 15, satisfaction: 87 },
    { timestamp: '10:30', profit: 12000, marketShare: 18, satisfaction: 92 },
    { timestamp: '10:45', profit: 15000, marketShare: 22, satisfaction: 94 },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <h1 className="text-3xl font-bold text-gray-900">
          FBA-Bench Dashboard
        </h1>
        <p className="text-gray-600 mt-2">Monitor your business agent simulations and performance metrics</p>
      </motion.div>

      {/* Connection Status Banner */}
      {(!connectionStatus.apiConnected || !connectionStatus.clearmlConnected) && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <XCircleIcon className="h-5 w-5 text-amber-400" />
              <div>
                <p className="text-amber-800 font-medium">Setup Required</p>
                <p className="text-amber-700 text-sm">
                  {!connectionStatus.clearmlConnected ? 'ClearML not connected' : 'API not connected'}
                </p>
              </div>
            </div>
            {!connectionStatus.clearmlConnected && (
              <button
                onClick={handleStartClearML}
                className="bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-lg transition-colors"
              >
                Start ClearML
              </button>
            )}
          </div>
        </motion.div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <MetricCard
          title="Total Experiments"
          value={mockStats.experiments?.total ?? 0}
          change={12}
          icon={BeakerIcon}
          color="text-blue-600"
        />
        <MetricCard
          title="Success Rate"
          value={`${mockStats.performance?.successRate || 95}%`}
          change={5}
          icon={CheckCircleIcon}
          color="text-green-600"
        />
        <MetricCard
          title="Top Score"
          value={mockStats.performance?.topScore || 95.2}
          change={-2}
          icon={TrophyIcon}
          color="text-amber-600"
        />
        <MetricCard
          title="Active Workers"
          value={mockStats.resources?.activeWorkers || 2}
          icon={CpuChipIcon}
          color="text-indigo-600"
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Real-time Performance Chart */}
        <motion.div
          className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <h3 className="text-gray-900 font-semibold mb-4 flex items-center">
            <ChartBarIcon className="h-5 w-5 mr-2 text-blue-600" />
            Real-time Performance
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={mockRealtimeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="timestamp" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #d1d5db',
                  borderRadius: '8px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Line type="monotone" dataKey="profit" stroke="#10b981" strokeWidth={3} dot={{ fill: '#10b981' }} />
              <Line type="monotone" dataKey="marketShare" stroke="#3b82f6" strokeWidth={2} dot={{ fill: '#3b82f6' }} />
            </LineChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Experiment Status Distribution */}
        <motion.div
          className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <h3 className="text-gray-900 font-semibold mb-4 flex items-center">
            <BeakerIcon className="h-5 w-5 mr-2 text-blue-600" />
            Experiment Status
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={[
                  { name: 'Completed', value: mockStats.experiments?.completed || 3, color: '#10b981' },
                  { name: 'Running', value: mockStats.experiments?.running || 1, color: '#3b82f6' },
                  { name: 'Failed', value: mockStats.experiments?.failed || 0, color: '#ef4444' },
                ]}
                cx="50%"
                cy="50%"
                outerRadius={100}
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {[
                  { name: 'Completed', value: mockStats.experiments?.completed || 3, color: '#10b981' },
                  { name: 'Running', value: mockStats.experiments?.running || 1, color: '#3b82f6' },
                  { name: 'Failed', value: mockStats.experiments?.failed || 0, color: '#ef4444' },
                ].map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </motion.div>
      </div>

      {/* Benchmark Runner */}
      <motion.div
        className="mb-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Benchmark Runner</h2>
              <p className="text-gray-600 text-sm">Configure the core engine and execute a benchmark run.</p>
            </div>
            <RocketLaunchIcon className="h-6 w-6 text-violet-500" />
          </div>

          <form onSubmit={handleRunBenchmark} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="flex flex-col text-sm font-medium text-gray-700">
                Scenario Key
                <input
                  type="text"
                  className="mt-1 rounded-md border border-gray-300 px-3 py-2 focus:border-violet-500 focus:ring-violet-500"
                  value={benchmarkForm.scenarioKey}
                  onChange={(event) => handleBenchmarkFieldChange('scenarioKey', event.target.value)}
                  placeholder="enterprise.default"
                  required
                />
              </label>
              <label className="flex flex-col text-sm font-medium text-gray-700">
                Runner Key
                <input
                  type="text"
                  className="mt-1 rounded-md border border-gray-300 px-3 py-2 focus:border-violet-500 focus:ring-violet-500"
                  value={benchmarkForm.runnerKey}
                  onChange={(event) => handleBenchmarkFieldChange('runnerKey', event.target.value)}
                  placeholder="async-runner"
                  required
                />
              </label>
            </div>

            <label className="flex flex-col text-sm font-medium text-gray-700">
              Scenario Parameters (JSON)
              <textarea
                className="mt-1 rounded-md border border-gray-300 px-3 py-2 h-24 focus:border-violet-500 focus:ring-violet-500"
                value={benchmarkForm.scenarioParams}
                onChange={(event) => handleBenchmarkFieldChange('scenarioParams', event.target.value)}
                placeholder='{"region":"us-east-1"}'
              />
            </label>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <label className="flex flex-col text-sm font-medium text-gray-700">
                Repetitions
                <input
                  type="number"
                  min={0}
                  className="mt-1 rounded-md border border-gray-300 px-3 py-2 focus:border-violet-500 focus:ring-violet-500"
                  value={benchmarkForm.repetitions}
                  onChange={(event) => handleBenchmarkFieldChange('repetitions', Number(event.target.value))}
                />
              </label>
              <label className="flex flex-col text-sm font-medium text-gray-700">
                Parallelism
                <input
                  type="number"
                  min={0}
                  className="mt-1 rounded-md border border-gray-300 px-3 py-2 focus:border-violet-500 focus:ring-violet-500"
                  value={benchmarkForm.parallelism}
                  onChange={(event) => handleBenchmarkFieldChange('parallelism', Number(event.target.value))}
                />
              </label>
              <label className="flex flex-col text-sm font-medium text-gray-700">
                Metrics (comma separated)
                <input
                  type="text"
                  className="mt-1 rounded-md border border-gray-300 px-3 py-2 focus:border-violet-500 focus:ring-violet-500"
                  value={benchmarkForm.metrics}
                  onChange={(event) => handleBenchmarkFieldChange('metrics', event.target.value)}
                  placeholder="throughput,success_rate"
                />
              </label>
            </div>

            <label className="flex flex-col text-sm font-medium text-gray-700">
              Validators (comma separated)
              <input
                type="text"
                className="mt-1 rounded-md border border-gray-300 px-3 py-2 focus:border-violet-500 focus:ring-violet-500"
                value={benchmarkForm.validators}
                onChange={(event) => handleBenchmarkFieldChange('validators', event.target.value)}
                placeholder="result_consistency"
              />
            </label>

            <div className="flex items-center justify-between">
              <button
                type="submit"
                disabled={isRunningBenchmark}
                className="inline-flex items-center justify-center rounded-md bg-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-violet-700 disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                {isRunningBenchmark ? 'Running…' : 'Run Benchmark'}
              </button>
              {benchmarkReport?.status && (
                <span className="text-sm font-medium text-gray-600">Status: {benchmarkReport.status}</span>
              )}
            </div>
          </form>

          <div className="mt-6">
            {benchmarkReport ? (
              <div className="rounded-md border border-gray-200 bg-gray-50 p-4">
                <h3 className="text-sm font-semibold text-gray-800 mb-2">Latest Benchmark Report</h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                  <div className="bg-white rounded-lg border border-gray-200 p-3">
                    <p className="text-xs text-gray-500 uppercase">Runs</p>
                    <p className="text-lg font-semibold text-gray-900">{benchmarkReport.totals?.runs ?? '—'}</p>
                  </div>
                  <div className="bg-white rounded-lg border border-gray-200 p-3">
                    <p className="text-xs text-gray-500 uppercase">Success</p>
                    <p className="text-lg font-semibold text-green-600">{benchmarkReport.totals?.success ?? '—'}</p>
                  </div>
                  <div className="bg-white rounded-lg border border-gray-200 p-3">
                    <p className="text-xs text-gray-500 uppercase">Failed</p>
                    <p className="text-lg font-semibold text-red-600">{benchmarkReport.totals?.failed ?? '—'}</p>
                  </div>
                </div>
                <pre className="overflow-x-auto whitespace-pre-wrap break-words text-xs text-gray-700 bg-white border border-gray-200 rounded-md p-3">
{JSON.stringify(benchmarkReport, null, 2)}
                </pre>
              </div>
            ) : (
              <p className="text-sm text-gray-500">Run a benchmark to see execution details from the core engine.</p>
            )}
          </div>
        </div>
      </motion.div>

      {/* Quick Actions */}
      <motion.div
        className="mb-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <QuickAction
            title="Launch New Experiment"
            description="Configure and start a business simulation"
            icon={RocketLaunchIcon}
            color="text-green-600"
            onClick={() => setShowLaunchModal(true)}
          />
          <QuickAction
            title="View All Experiments"
            description="Browse and manage simulations"
            icon={BeakerIcon}
            color="text-blue-600"
            onClick={() => window.location.href = '/experiments'}
          />
          <QuickAction
            title="Check Leaderboard"
            description="See top performing agents"
            icon={TrophyIcon}
            color="text-amber-600"
            onClick={() => window.location.href = '/leaderboard'}
          />
        </div>
      </motion.div>

      {/* Recent Experiments */}
      <motion.div
        className="bg-white border border-gray-200 rounded-lg shadow-sm"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900 flex items-center">
            <ClockIcon className="h-5 w-5 mr-2 text-gray-400" />
            Recent Experiments
          </h2>
        </div>
        <div className="p-6">
          {experiments.length > 0 ? (
            <div className="space-y-4">
              {experiments.slice(0, 5).map((experiment) => (
                <motion.div
                  key={experiment.id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
                  whileHover={{ x: 5 }}
                >
                  <div className="flex items-center space-x-4">
                    <div className={`w-3 h-3 rounded-full ${
                      experiment.status === 'completed' ? 'bg-green-500' :
                      experiment.status === 'running' ? 'bg-blue-500' :
                      experiment.status === 'failed' ? 'bg-red-500' :
                      'bg-amber-500'
                    }`} />
                    <div>
                      <p className="text-gray-900 font-medium">{experiment.name}</p>
                      <p className="text-gray-600 text-sm">{experiment.status}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-gray-900">{experiment.metrics?.profit ? `$${experiment.metrics.profit.toLocaleString()}` : 'N/A'}</p>
                    <p className="text-gray-600 text-sm">{new Date(experiment.updated).toLocaleDateString()}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <BeakerIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-gray-900 font-medium mb-2">No Experiments Yet</h3>
              <p className="text-gray-600 mb-6">Start your first business simulation to see results here</p>
              <button
                onClick={() => setShowLaunchModal(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium transition-all duration-200 flex items-center justify-center space-x-2"
              >
                <RocketLaunchIcon className="h-4 w-4" />
                <span>Launch First Experiment</span>
              </button>
            </div>
          )}
        </div>
      </motion.div>

      {/* Launch Modal */}
      <LaunchModal
        isOpen={showLaunchModal}
        onClose={() => setShowLaunchModal(false)}
        onLaunch={handleLaunchExperiment}
      />
    </div>
  );
};

export default Dashboard;