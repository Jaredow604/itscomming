import { useState } from 'react';
import { Loader2, Zap, History, Award, ChevronDown, ChevronUp } from 'lucide-react';
import PickCard from './PickCard';
import PlayerPickCard from './PlayerPickCard';
import { useBestPicks } from '../../hooks/useBestPicks';
import { usePlayerProps } from '../../hooks/usePlayerProps';

export default function BestPicksPanel() {
  const { data, isLoading, error } = useBestPicks();
  const { data: playerData, isLoading: playerLoading, error: playerError } = usePlayerProps('all', 0);
  const [showHistory, setShowHistory] = useState(false);
  const [pickType, setPickType] = useState<'team' | 'player'>('team');

  const topPlayerProps = playerData?.props?.slice(0, 6) || [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200/60 dark:border-white/10">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" />
            <h2 className="text-sm font-bold text-slate-800 dark:text-white">Top Picks del Día</h2>
          </div>

          {/* Toggle: Team / Player */}
          <div className="flex items-center bg-slate-100 dark:bg-white/5 rounded-lg p-0.5">
            <button
              onClick={() => setPickType('team')}
              className={`text-[9px] font-bold px-2 py-1 rounded-md transition-all ${
                pickType === 'team'
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
              }`}
            >
              Teams
            </button>
            <button
              onClick={() => setPickType('player')}
              className={`text-[9px] font-bold px-2 py-1 rounded-md transition-all ${
                pickType === 'player'
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
              }`}
            >
              Players
            </button>
          </div>
        </div>

        {/* Record */}
        {data?.record && pickType === 'team' && (
          <div className="flex items-center gap-2 mt-1">
            <div className="flex items-center gap-1">
              <Award className="w-3 h-3 text-emerald-500" />
              <span className="text-[10px] font-semibold text-emerald-500">
                {data.record.wins}W - {data.record.losses}L
              </span>
            </div>
            <div className="w-px h-3 bg-slate-200 dark:bg-white/10" />
            <span className="text-[10px] text-slate-400 dark:text-slate-500">
              Win rate: {data.record.win_rate}%
            </span>
          </div>
        )}

        {/* Player props summary */}
        {pickType === 'player' && playerData?.summary && (
          <div className="flex items-center gap-2 mt-1">
            <span className="text-[10px] font-semibold text-emerald-500">
              {playerData.summary.total} props
            </span>
            <div className="w-px h-3 bg-slate-200 dark:bg-white/10" />
            <span className="text-[10px] text-slate-400 dark:text-slate-500">
              Avg EV: +{playerData.summary.avg_ev}%
            </span>
            {playerData.summary.high_confidence_count > 0 && (
              <>
                <div className="w-px h-3 bg-slate-200 dark:bg-white/10" />
                <span className="text-[10px] font-semibold text-amber-500">
                  {playerData.summary.high_confidence_count} high conf
                </span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {pickType === 'team' ? (
          /* ===== TEAM PICKS ===== */
          <>
            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />
              </div>
            )}

            {error && (
              <div className="text-center py-8">
                <p className="text-xs text-red-400">Error cargando picks</p>
              </div>
            )}

            {!isLoading && !error && data?.today && data.today.length === 0 && (
              <div className="text-center py-8">
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  Sin picks generados hoy
                </p>
              </div>
            )}

            {!isLoading && !error && data?.today?.map((pick, i) => (
              <PickCard key={`today-${pick.home_team}-${pick.away_team}-${i}`} pick={pick} index={i} isHistorical={false} />
            ))}

            {/* Historical picks toggle */}
            {data?.history && data.history.length > 0 && (
              <div className="pt-2">
                <button
                  onClick={() => setShowHistory(!showHistory)}
                  className="flex items-center gap-2 w-full px-3 py-2 rounded-lg
                             bg-slate-100/80 dark:bg-white/5 hover:bg-slate-200/80 dark:hover:bg-white/10
                             transition-colors duration-200"
                >
                  <History className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-[10px] font-semibold text-slate-500 dark:text-slate-400">
                    Historial de Picks ({data.history.length})
                  </span>
                  {showHistory ? (
                    <ChevronUp className="w-3 h-3 text-slate-400 ml-auto" />
                  ) : (
                    <ChevronDown className="w-3 h-3 text-slate-400 ml-auto" />
                  )}
                </button>

                {showHistory && (
                  <div className="mt-2 space-y-2">
                    {data.history.map((pick, i) => (
                      <PickCard key={`hist-${pick.date}-${pick.home_team}-${i}`} pick={pick} index={i} isHistorical />
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          /* ===== PLAYER PICKS ===== */
          <>
            {playerLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />
              </div>
            )}

            {playerError && (
              <div className="text-center py-8">
                <p className="text-xs text-red-400">Error cargando player props</p>
              </div>
            )}

            {!playerLoading && !playerError && topPlayerProps.length === 0 && (
              <div className="text-center py-8">
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  Sin player props disponibles
                </p>
              </div>
            )}

            {!playerLoading && !playerError && topPlayerProps.map((player, i) => (
              <PlayerPickCard key={player.id} player={player} index={i} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
