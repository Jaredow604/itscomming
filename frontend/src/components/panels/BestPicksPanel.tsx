import { useState } from 'react';
import { Loader2, Zap, History, Award, ChevronDown, ChevronUp } from 'lucide-react';
import PickCard from './PickCard';
import { useBestPicks } from '../../hooks/useBestPicks';

export default function BestPicksPanel() {
  const { data, isLoading, error } = useBestPicks();
  const [showHistory, setShowHistory] = useState(false);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200/60 dark:border-white/10">
        <div className="flex items-center gap-2 mb-1">
          <Zap className="w-4 h-4 text-amber-500" />
          <h2 className="text-sm font-bold text-slate-800 dark:text-white">Top Picks del Día</h2>
        </div>

        {/* Record */}
        {data?.record && (
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
      </div>

      {/* Today picks */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
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
      </div>
    </div>
  );
}
