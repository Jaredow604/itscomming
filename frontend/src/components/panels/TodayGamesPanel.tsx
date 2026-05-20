import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import { Loader2, Calendar } from 'lucide-react';
import GameCard from './GameCard';
import { useTodayGames } from '../../hooks/useTodayGames';
import type { Sport } from '../../types';

interface TodayGamesPanelProps {
  sport: Sport | 'all';
  isDark: boolean;
}

export default function TodayGamesPanel({ sport, isDark }: TodayGamesPanelProps) {
  const { data: games, isLoading, error } = useTodayGames(sport === 'all' ? undefined : sport);

  const today = format(new Date(), "EEEE d 'de' MMMM", { locale: es });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200/60 dark:border-white/10">
        <div className="flex items-center gap-2 mb-1">
          <Calendar className="w-4 h-4 text-brand-500" />
          <h2 className="text-sm font-bold text-slate-800 dark:text-white">Partidos de Hoy</h2>
        </div>
        <p className="text-[11px] text-slate-400 dark:text-slate-500 capitalize">{today}</p>
      </div>

      {/* Games list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />
            <span className="ml-2 text-xs text-slate-400">Cargando...</span>
          </div>
        )}

        {error && (
          <div className="text-center py-8">
            <p className="text-xs text-red-400">Error cargando partidos</p>
          </div>
        )}

        {!isLoading && !error && games && games.length === 0 && (
          <div className="text-center py-8">
            <p className="text-xs text-slate-400 dark:text-slate-500">
              No hay partidos para hoy
            </p>
            <p className="text-[10px] text-slate-400 dark:text-slate-600 mt-1">
              Usa el chatbot para analizar cualquier matchup
            </p>
          </div>
        )}

        {!isLoading && !error && games && games.map((game, i) => (
          <GameCard
            key={`${game.home_team}-${game.away_team}-${i}`}
            game={game}
            index={i}
            isDark={isDark}
          />
        ))}
      </div>
    </div>
  );
}
