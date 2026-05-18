import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { H2HStat } from '../../types';

interface H2HStatsChartProps {
  data: H2HStat[];
  homeTeam: string;
  awayTeam: string;
  isDark: boolean;
}

/**
 * H2HStatsChart — RadarChart comparing key metrics between home and away teams.
 *
 * Uses semi-transparent fills for visual overlap clarity.
 * PolarAngleAxis labels adapt color to theme.
 */
export default function H2HStatsChart({
  data,
  homeTeam,
  awayTeam,
  isDark,
}: H2HStatsChartProps) {
  // Normalize values to 0-100 scale for radar visualization
  const maxValues = data.reduce(
    (acc, item) => {
      const max = Math.max(item.home, item.away);
      return { ...acc, [item.stat]: max };
    },
    {} as Record<string, number>,
  );

  const chartData = data.map((item) => {
    const scale = maxValues[item.stat] || 1;
    return {
      stat: item.stat,
      home: Math.round((item.home / scale) * 100),
      away: Math.round((item.away / scale) * 100),
      homeRaw: item.home,
      awayRaw: item.away,
    };
  });

  const labelColor = isDark ? '#94a3b8' : '#64748b';
  const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';

  return (
    <div className="w-full">
      <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
        Head-to-Head Comparison
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <RadarChart data={chartData} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke={gridColor} />
          <PolarAngleAxis
            dataKey="stat"
            tick={{ fontSize: 9, fill: labelColor }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={false}
            axisLine={false}
          />
          <Radar
            name={homeTeam}
            dataKey="home"
            stroke="#10b981"
            fill="#10b981"
            fillOpacity={0.2}
            strokeWidth={2}
          />
          <Radar
            name={awayTeam}
            dataKey="away"
            stroke="#f43f5e"
            fill="#f43f5e"
            fillOpacity={0.15}
            strokeWidth={2}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px', color: labelColor }}
            iconType="circle"
            iconSize={8}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
