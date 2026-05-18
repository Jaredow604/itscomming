import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import type { EloTrend } from '../../types';

interface EloTrendChartProps {
  data: EloTrend;
  homeTeam: string;
  awayTeam: string;
  isDark: boolean;
}

/**
 * EloTrendChart — LineChart showing Elo rating evolution for the last N games.
 *
 * Two lines: home team (emerald) and away team (rose).
 * Fully theme-aware: axis colors, grid, tooltip background all adapt.
 */
export default function EloTrendChart({
  data,
  homeTeam,
  awayTeam,
  isDark,
}: EloTrendChartProps) {
  // Transform arrays into Recharts-compatible data
  const chartData = data.labels.map((label, i) => ({
    game: label,
    home: data.home[i],
    away: data.away[i],
  }));

  const axisColor = isDark ? '#64748b' : '#94a3b8';
  const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
  const tooltipBg = isDark ? '#1e293b' : '#ffffff';
  const tooltipBorder = isDark ? '#334155' : '#e2e8f0';

  return (
    <div className="w-full">
      <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
        Elo Rating — Last {data.labels.length} Games
      </p>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
          <CartesianGrid stroke={gridColor} strokeDasharray="3 3" />
          <XAxis
            dataKey="game"
            tick={{ fontSize: 10, fill: axisColor }}
            axisLine={{ stroke: gridColor }}
            tickLine={false}
          />
          <YAxis
            domain={['dataMin - 20', 'dataMax + 20']}
            tick={{ fontSize: 10, fill: axisColor }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: tooltipBg,
              border: `1px solid ${tooltipBorder}`,
              borderRadius: '10px',
              fontSize: '12px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            }}
            labelStyle={{ fontWeight: 600 }}
          />
          <Line
            type="monotone"
            dataKey="home"
            stroke="#10b981"
            strokeWidth={2.5}
            dot={{ r: 3, fill: '#10b981' }}
            activeDot={{ r: 5 }}
            name={homeTeam}
          />
          <Line
            type="monotone"
            dataKey="away"
            stroke="#f43f5e"
            strokeWidth={2.5}
            dot={{ r: 3, fill: '#f43f5e' }}
            activeDot={{ r: 5 }}
            name={awayTeam}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
