import { useState } from 'react';
import { Loader2, Trophy, AlertCircle } from 'lucide-react';
import TeamLogo from '../ui/TeamLogo';
import { useStandings } from '../../hooks/useStandings';

const LEAGUES = [
  { key: 'premier', label: 'Premier League', icon: '🏴󠁧󠁢󠁥󠁮󠁧󠁿' },
  { key: 'laliga', label: 'La Liga', icon: '🇪🇸' },
  { key: 'seriea', label: 'Serie A', icon: '🇮' },
  { key: 'bundesliga', label: 'Bundesliga', icon: '🇪' },
  { key: 'ligue1', label: 'Ligue 1', icon: '🇫🇷' },
  { key: 'ligamx', label: 'Liga MX', icon: '🇲' },
  { key: 'nba', label: 'NBA', icon: '' },
  { key: 'mlb', label: 'MLB', icon: '⚾' },
];

interface LeagueStandingsProps {
  isDark: boolean;
}

function PositionBadge({ pos }: { pos: number }) {
  let color = 'bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400';
  if (pos === 1) color = 'bg-amber-500/15 text-amber-600 dark:text-amber-400';
  else if (pos === 2) color = 'bg-slate-300/30 text-slate-600 dark:text-slate-300';
  else if (pos === 3) color = 'bg-orange-500/15 text-orange-600 dark:text-orange-400';
  else if (pos <= 4) color = 'bg-blue-500/10 text-blue-600 dark:text-blue-400';

  return (
    <span className={`w-6 h-6 flex items-center justify-center rounded-md text-[10px] font-bold ${color}`}>
      {pos}
    </span>
  );
}

export default function LeagueStandings({ isDark: _isDark }: LeagueStandingsProps) {
  const [activeLeague, setActiveLeague] = useState('premier');
  const [activeSeason, setActiveSeason] = useState('25-26');
  const { data, isLoading, error } = useStandings(activeLeague, activeSeason);

  const isUSLeague = activeLeague === 'nba' || activeLeague === 'mlb';
  const seasons = data?.available_seasons || ['25-26', '24-25', '23-24'];

  return (
    <div className="flex flex-col h-full">
      {/* League selector */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200/60 dark:border-white/10">
        <div className="flex items-center gap-2 mb-3">
          <Trophy className="w-4 h-4 text-amber-500" />
          <h2 className="text-sm font-bold text-slate-800 dark:text-white">Tabla de Clasificacion</h2>
        </div>
        <div className="flex gap-1 overflow-x-auto pb-1 scrollbar-hide">
          {LEAGUES.map(l => (
            <button
              key={l.key}
              onClick={() => setActiveLeague(l.key)}
              className={`whitespace-nowrap px-2.5 py-1 rounded-full text-[10px] font-bold transition-colors
                ${activeLeague === l.key
                  ? 'bg-slate-800 text-white dark:bg-white dark:text-slate-900'
                  : 'bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-white/5 dark:text-slate-400 dark:hover:bg-white/10'}`}
            >
              {l.icon} {l.label}
            </button>
          ))}
        </div>

        {/* Season selector */}
        {!isUSLeague && (
          <div className="flex items-center gap-1.5 mt-2">
            <span className="text-[9px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
              Temporada:
            </span>
            <div className="flex gap-1">
              {seasons.map(s => (
                <button
                  key={s}
                  onClick={() => setActiveSeason(s)}
                  className={`whitespace-nowrap px-2 py-0.5 rounded-md text-[9px] font-bold transition-all
                    ${activeSeason === s
                      ? 'bg-brand-500/20 text-brand-600 dark:text-brand-400 border border-brand-500/30'
                      : 'bg-slate-100 dark:bg-white/5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 border border-transparent'}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Table header */}
      <div className="flex-shrink-0 px-4 py-2 border-b border-slate-200/40 dark:border-white/5
                      bg-slate-50/80 dark:bg-white/[0.02]">
        <div className="flex items-center gap-2 text-[9px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
          <span className="w-7 text-center">#</span>
          <span className="w-7 flex-shrink-0"></span>
          <span className="flex-1 min-w-[120px]">Equipo</span>
          {isUSLeague ? (
            <>
              <span className="w-8 text-center">W</span>
              <span className="w-8 text-center">L</span>
              <span className="w-10 text-center">PCT</span>
            </>
          ) : (
            <>
              <span className="w-8 text-center">PJ</span>
              <span className="w-8 text-center">PG</span>
              <span className="w-8 text-center">PE</span>
              <span className="w-8 text-center">PP</span>
              <span className="w-8 text-center">GF</span>
              <span className="w-8 text-center">GC</span>
              <span className="w-10 text-center">DG</span>
              <span className="w-10 text-center">PTS</span>
            </>
          )}
        </div>
      </div>

      {/* Table body */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />
            <span className="ml-2 text-xs text-slate-400">Cargando tabla...</span>
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center py-12 px-4">
            <AlertCircle className="w-8 h-8 text-red-400 mb-3" />
            <p className="text-xs text-red-400 font-semibold mb-1">Error al cargar la tabla</p>
            <p className="text-[10px] text-slate-400 text-center">
              Verifica que el backend este corriendo y haya datos de partidos jugados.
            </p>
          </div>
        )}

        {!isLoading && !error && (!data?.standings || data.standings.length === 0) && (
          <div className="flex flex-col items-center justify-center py-12 px-4">
            <Trophy className="w-8 h-8 text-slate-300 dark:text-slate-600 mb-3" />
            <p className="text-xs text-slate-400 font-semibold mb-1">Sin datos disponibles</p>
            <p className="text-[10px] text-slate-400 text-center">
              No hay partidos registrados para esta liga todavia.
            </p>
          </div>
        )}

        {!isLoading && !error && data?.standings?.map((standing, idx) => (
          <div
            key={standing.team_id}
            className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-100/60 dark:border-white/5
                       hover:bg-slate-50/80 dark:hover:bg-white/[0.03] transition-colors"
          >
            <PositionBadge pos={idx + 1} />
            <TeamLogo url={standing.logo_url} name={standing.team_name} size="sm" className="flex-shrink-0" />
            <span className="flex-1 min-w-[120px] text-[11px] font-medium text-slate-700 dark:text-slate-200 truncate">
              {standing.team_name}
            </span>
            {isUSLeague ? (
              <>
                <span className="w-8 text-center text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">
                  {standing.wins}
                </span>
                <span className="w-8 text-center text-[10px] text-red-500 dark:text-red-400 font-semibold">
                  {standing.losses}
                </span>
                <span className="w-10 text-center text-[10px] font-bold text-slate-600 dark:text-slate-300">
                  {standing.played > 0 ? (standing.wins / standing.played).toFixed(3).slice(1) : '.000'}
                </span>
              </>
            ) : (
              <>
                <span className="w-8 text-center text-[10px] text-slate-500 dark:text-slate-400">
                  {standing.played}
                </span>
                <span className="w-8 text-center text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">
                  {standing.wins}
                </span>
                <span className="w-8 text-center text-[10px] text-slate-500 dark:text-slate-400">
                  {standing.draws}
                </span>
                <span className="w-8 text-center text-[10px] text-red-500 dark:text-red-400 font-semibold">
                  {standing.losses}
                </span>
                <span className="w-8 text-center text-[10px] text-slate-600 dark:text-slate-300">
                  {standing.goals_for}
                </span>
                <span className="w-8 text-center text-[10px] text-slate-600 dark:text-slate-300">
                  {standing.goals_against}
                </span>
                <span className={`w-10 text-center text-[10px] font-semibold
                  ${standing.goal_diff > 0 ? 'text-emerald-600 dark:text-emerald-400' :
                    standing.goal_diff < 0 ? 'text-red-500 dark:text-red-400' :
                    'text-slate-400 dark:text-slate-500'}`}>
                  {standing.goal_diff > 0 ? '+' : ''}{standing.goal_diff}
                </span>
                <span className="w-10 text-center text-[10px] font-bold text-slate-800 dark:text-white">
                  {standing.points}
                </span>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
