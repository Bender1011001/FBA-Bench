import React, { useEffect, useState } from 'react';
import { useSimulationStream } from '../hooks/useSimulationStream';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface DashboardProps {
  token?: string | null;
}

const Dashboard: React.FC<DashboardProps> = ({ token }) => {
  const [dataPoints, setDataPoints] = useState<any[]>([]);
  const { isConnected, lastEvent, snapshot } = useSimulationStream({
    token,
    topics: ['simulation.metrics', 'simulation.snapshot'],
  });

  // Accumulate data points for the chart
  useEffect(() => {
    if (lastEvent?.topic === 'simulation.metrics') {
      setDataPoints((prev) => {
        const newPoint = {
          tick: lastEvent.data.tick,
          revenue: lastEvent.data.revenue,
          profit: lastEvent.data.profit,
          timestamp: lastEvent.ts,
        };
        // Keep last 50 points
        return [...prev, newPoint].slice(-50);
      });
    }
  }, [lastEvent]);

  // Use snapshot for initial state or status updates
  const status = snapshot?.status || 'unknown';
  const currentTick = snapshot?.tick || 0;
  const kpis = snapshot?.kpis || { revenue: 0, profit: 0, units_sold: 0 };

  return (
    <div className="dashboard-container" style={{ padding: '20px', width: '100%', maxWidth: '1200px' }}>
      <div className="dashboard-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2>Simulation Dashboard</h2>
        <div className="status-indicator">
          <span
            style={{
              display: 'inline-block',
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: isConnected ? '#28a745' : '#dc3545',
              marginRight: '8px',
            }}
          />
          {isConnected ? 'Connected' : 'Disconnected'} ({status})
        </div>
      </div>

      <div className="kpi-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', marginBottom: '30px' }}>
        <div className="kpi-card" style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '8px', backgroundColor: '#f8f9fa' }}>
          <h3>Current Tick</h3>
          <p style={{ fontSize: '24px', fontWeight: 'bold' }}>{currentTick}</p>
        </div>
        <div className="kpi-card" style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '8px', backgroundColor: '#f8f9fa' }}>
          <h3>Revenue</h3>
          <p style={{ fontSize: '24px', fontWeight: 'bold', color: '#007bff' }}>
            ${kpis.revenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
        </div>
        <div className="kpi-card" style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '8px', backgroundColor: '#f8f9fa' }}>
          <h3>Profit</h3>
          <p style={{ fontSize: '24px', fontWeight: 'bold', color: kpis.profit >= 0 ? '#28a745' : '#dc3545' }}>
            ${kpis.profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
        </div>
        <div className="kpi-card" style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '8px', backgroundColor: '#f8f9fa' }}>
          <h3>Units Sold</h3>
          <p style={{ fontSize: '24px', fontWeight: 'bold' }}>{kpis.units_sold.toLocaleString()}</p>
        </div>
      </div>

      <div className="chart-container" style={{ height: '400px', border: '1px solid #ddd', borderRadius: '8px', padding: '20px', backgroundColor: '#fff' }}>
        <h3>Financial Performance</h3>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={dataPoints}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="tick" label={{ value: 'Tick', position: 'insideBottomRight', offset: -5 }} />
            <YAxis yAxisId="left" label={{ value: 'Revenue ($)', angle: -90, position: 'insideLeft' }} />
            <YAxis yAxisId="right" orientation="right" label={{ value: 'Profit ($)', angle: 90, position: 'insideRight' }} />
            <Tooltip
              formatter={(value: number) => [`$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, '']}
              labelFormatter={(label: any) => `Tick: ${label}`}
            />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="revenue" stroke="#007bff" activeDot={{ r: 8 }} name="Revenue" />
            <Line yAxisId="right" type="monotone" dataKey="profit" stroke="#28a745" name="Profit" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {snapshot?.agents && snapshot.agents.length > 0 && (
        <div className="agents-list" style={{ marginTop: '30px' }}>
          <h3>Active Agents</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '15px' }}>
            {snapshot.agents.map((agent) => (
              <div key={agent.slug} style={{ padding: '10px', border: '1px solid #eee', borderRadius: '4px' }}>
                <strong>{agent.display_name}</strong>
                <div style={{ fontSize: '0.9em', color: '#666' }}>State: {agent.state}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;