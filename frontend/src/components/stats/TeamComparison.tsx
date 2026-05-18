import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend, ResponsiveContainer, Tooltip } from 'recharts';
import { X, MessageSquare } from 'lucide-react';
import type { TeamComparison as TeamComparisonType } from '../../types';
import TeamLogo from '../ui/TeamLogo';

interface TeamComparisonProps {
  comparison: TeamComparisonType;
  onClose: () => void;
  onChat: (message: string) => void;
}

export default function TeamComparison({ comparison, onClose, onChat }: TeamComparisonProps) {
  const [team1, team2] = comparison.teams;
  if (!team1 || !team2) return null;

  const maxGoals = Math.max(team1.prom_goles, team2.prom_goles, 0.1);
  const maxShots = Math.max(team1.prom_tiros_puerta, team2.prom_tiros_puerta, 0.1);
  const maxCorners = Math.max(team1.prom_corners, team2.prom_corners, 0.1);

  const normalizedRadarData = [
    { metric: 'Goles', t1: (team1.prom_goles / maxGoals) * 100, t2: (team2.prom_goles / maxGoals) * 100 },
    { metric: 'Tiros', t1: (team1.prom_tiros_puerta / maxShots) * 100, t2: (team2.prom_tiros_puerta / maxShots) * 100 },
    { metric: 'Corners', t1: (team1.prom_corners / maxCorners) * 100, t2: (team2.prom_corners / maxCorners) * 100 },
  ];

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-slate-800 dark:text-white">
          Comparación de Equipos
        </h2>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/5 transition-colors"
        >
          <X className="w-4 h-4 text-slate-400" />
        </button>
      </div>

      {/* Teams header */}
      <div className="glass-card p-4">
        {/* Matchup Header */}
        <div className="flex items-center justify-between mb-8 relative">
          <div className="flex-1 text-center flex flex-col items-center">
            <TeamLogo name={team1.name} size="xl" className="mb-3 ring-4 ring-brand-500/20" />
            <h3 className="text-xl font-bold text-slate-800 dark:text-white">
              {team1.name}
            </h3>
            <span className="text-sm text-slate-500 dark:text-slate-400 mt-1">Local</span>
          </div>
          
          <div className="px-4 text-center z-10">
            <div className="bg-slate-100 dark:bg-slate-800 rounded-full p-3 border border-slate-200 dark:border-slate-700 shadow-sm">
              <span className="text-sm font-black text-slate-400 dark:text-slate-500">VS</span>
            </div>
          </div>
          
          <div className="flex-1 text-center flex flex-col items-center">
            <TeamLogo name={team2.name} size="xl" className="mb-3 ring-4 ring-slate-500/20" />
            <h3 className="text-xl font-bold text-slate-800 dark:text-white">
              {team2.name}
            </h3>
            <span className="text-sm text-slate-500 dark:text-slate-400 mt-1">Visitante</span>
          </div>
          
          {/* Decorative line */}
          <div className="absolute left-1/4 right-1/4 top-[40px] h-px bg-gradient-to-r from-transparent via-slate-200 dark:via-slate-700 to-transparent -z-10" />
        </div>
      </div>

      {/* Side-by-side metrics */}
      <div className="grid grid-cols-2 gap-3">
        <TeamMetricCard team={team1.name} label="Goles/Juego" value={team1.prom_goles.toFixed(2)} isLeft />
        <TeamMetricCard team={team2.name} label="Goles/Juego" value={team2.prom_goles.toFixed(2)} />
        <TeamMetricCard team={team1.name} label="Tiros a Puerta" value={team1.prom_tiros_puerta.toFixed(1)} isLeft />
        <TeamMetricCard team={team2.name} label="Tiros a Puerta" value={team2.prom_tiros_puerta.toFixed(1)} />
        <TeamMetricCard team={team1.name} label="Corners/Juego" value={team1.prom_corners.toFixed(1)} isLeft />
        <TeamMetricCard team={team2.name} label="Corners/Juego" value={team2.prom_corners.toFixed(1)} />
      </div>

      {/* Advantages */}
      {comparison.advantages.length > 0 && (
        <div className="glass-card p-4">
          <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
            Ventajas por métrica
          </h3>
          <div className="space-y-2">
            {comparison.advantages.map((adv: string, i: number) => (
              <div key={i} className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-brand-500" />
                <span className="text-xs text-slate-600 dark:text-slate-300">{adv}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Radar chart */}
      <div className="glass-card p-4">
        <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
          Radar Comparativo
        </h3>
        <ResponsiveContainer width="100%" height={250}>
          <RadarChart data={normalizedRadarData}>
            <PolarGrid stroke="rgba(148,163,184,0.2)" />
            <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10, fill: '#94a3b8' }} />
            <PolarRadiusAxis tick={false} axisLine={false} />
            <Radar name={team1.name} dataKey="t1" stroke="#10b981" fill="#10b981" fillOpacity={0.2} strokeWidth={2} />
            <Radar name={team2.name} dataKey="t2" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.2} strokeWidth={2} />
            <Legend wrapperStyle={{ fontSize: '10px' }} />
            <Tooltip
              contentStyle={{
                background: '#1e293b',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                fontSize: '11px',
              }}
              formatter={(value) => `${Number(value).toFixed(0)}%`}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* CTA */}
      <button
        onClick={() => onChat(`${team1.name} vs ${team2.name}`)}
        className="flex items-center gap-2 w-full justify-center px-4 py-3 rounded-xl
                   bg-gradient-to-r from-brand-500 to-cyan-500 hover:from-brand-600 hover:to-cyan-600
                   text-white text-sm font-bold transition-all duration-200 shadow-lg shadow-brand-500/20"
      >
        <MessageSquare className="w-4 h-4" />
        Analizar {team1.name} vs {team2.name} en el Chatbot
      </button>
    </div>
  );
}

function TeamMetricCard({
  team,
  label,
  value,
  isLeft,
}: {
  team: string;
  label: string;
  value: string;
  isLeft?: boolean;
}) {
  return (
    <div className={`rounded-xl px-3 py-2.5 text-center
      ${isLeft
        ? 'bg-emerald-500/5 border border-emerald-500/10'
        : 'bg-rose-500/5 border border-rose-500/10'
      }`}>
      <p className="text-[9px] text-slate-400 uppercase tracking-wider">{team}</p>
      <p className={`text-[10px] text-slate-500 dark:text-slate-400`}>{label}</p>
      <p className={`text-base font-bold font-mono
        ${isLeft ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
        {value}
      </p>
    </div>
  );
}
