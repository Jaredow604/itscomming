import { Clock, MapPin, Zap, Target, MessageSquare } from 'lucide-react';
import FormBadge from './FormBadge';
import MetricBarChart from './MetricBarChart';
import type { TeamDetail as TeamDetailType, TeamStatsEntry } from '../../types';

interface TeamDetailPanelProps {
  detail: TeamDetailType;
  teams: TeamStatsEntry[];
  isDark: boolean;
  compareMode: boolean;
  onCompare: () => void;
  onChat: (message: string) => void;
}

export default function TeamDetailPanel({
  detail,
  teams,
  isDark,
  compareMode,
  onCompare,
  onChat,
}: TeamDetailPanelProps) {
  const chartData = [
    { metric: 'Goles', value: detail.prom_goles },
    { metric: 'Tiros', value: detail.prom_tiros_puerta },
    { metric: 'Corners', value: detail.prom_corners },
  ];

  // Simulated form (in real app this would come from API)
  const form = ['W', 'W', 'D', 'W', 'L'];

  // Find an opponent for comparison
  const otherTeams = teams.filter((t) => t.name !== detail.name);
  const topOpponent = otherTeams[0];

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      {/* ====== HEADER ====== */}
      <div className="glass-card p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-500 to-cyan-500
                           flex items-center justify-center text-2xl font-bold text-white shadow-lg shadow-brand-500/20">
              {detail.name.charAt(0)}
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-800 dark:text-white">{detail.name}</h1>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                Métricas avanzadas
              </p>
            </div>
          </div>

          {compareMode && (
            <button
              onClick={onCompare}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                         bg-brand-500/10 text-brand-600 dark:text-brand-400
                         text-xs font-semibold hover:bg-brand-500/20 transition-colors"
            >
              <Target className="w-3.5 h-3.5" />
              Seleccionar rival
            </button>
          )}
        </div>

        {/* Match today banner */}
        {detail.match_today && (
          <div className="mt-4 p-3 rounded-xl bg-gradient-to-r from-brand-500/10 to-cyan-500/10
                         border border-brand-500/20 dark:border-brand-400/20">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="w-4 h-4 text-brand-500" />
              <span className="text-xs font-bold text-brand-600 dark:text-brand-400">
                PARTIDO HOY
              </span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MapPin className={`w-3.5 h-3.5 ${detail.match_today.home_away === 'home' ? 'text-emerald-500' : 'text-blue-500'}`} />
                <span className="text-sm font-bold text-slate-800 dark:text-white">
                  {detail.match_today.full_match}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-xs font-mono font-bold text-slate-600 dark:text-slate-300">
                  {detail.match_today.start_time}
                </span>
              </div>
            </div>

            {/* CTA */}
            <button
              onClick={() => detail.match_today && onChat(`${detail.match_today.full_match}`)}
              className="mt-3 flex items-center gap-1.5 w-full justify-center px-4 py-2 rounded-lg
                         bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold
                         transition-colors duration-200"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Analizar en el Chatbot
            </button>
          </div>
        )}
      </div>

      {/* ====== KEY METRICS ====== */}
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="Goles/Juego" value={detail.prom_goles.toFixed(2)} highlight />
        <MetricCard label="Tiros a Puerta" value={detail.prom_tiros_puerta.toFixed(1)} />
        <MetricCard label="Corners/Juego" value={detail.prom_corners.toFixed(1)} />
      </div>

      {/* ====== FORM ====== */}
      <div className="glass-card p-4">
        <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
          Forma Reciente (últimos 5)
        </h3>
        <div className="flex items-center gap-2">
          {form.map((r, i) => (
            <FormBadge key={i} result={r} />
          ))}
          <span className="ml-2 text-xs text-slate-400">
            {form.filter((r) => r === 'W').length}W {form.filter((r) => r === 'D').length}D {form.filter((r) => r === 'L').length}L
          </span>
        </div>
      </div>

      {/* ====== BAR CHART ====== */}
      <div className="glass-card p-4">
        <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
          Métricas por Partido
        </h3>
        <MetricBarChart data={chartData} color="#3b82f6" isDark={isDark} />
      </div>

      {/* ====== SUGGEST COMPARISON ====== */}
      {topOpponent && !compareMode && (
        <div className="glass-card p-4">
          <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
            Comparar con
          </h3>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-white/10
                           flex items-center justify-center text-xs font-bold text-slate-500">
              {topOpponent.name.charAt(0)}
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">{topOpponent.name}</p>
              <p className="text-[10px] text-slate-400">{topOpponent.prom_goles.toFixed(2)} goles/juego</p>
            </div>
            <button
              onClick={onCompare}
              className="px-3 py-1.5 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400
                         text-xs font-semibold hover:bg-brand-500/20 transition-colors"
            >
              Comparar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={`rounded-xl px-4 py-3 text-center
      ${highlight
        ? 'bg-brand-500/10 border border-brand-500/20'
        : 'bg-slate-100/80 dark:bg-white/5 border border-slate-200/40 dark:border-white/5'
      }`}>
      <p className="text-[10px] text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className={`text-lg font-bold font-mono
        ${highlight ? 'text-brand-600 dark:text-brand-400' : 'text-slate-800 dark:text-white'}`}>
        {value}
      </p>
    </div>
  );
}
