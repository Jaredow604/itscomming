import { motion } from 'framer-motion';
import { Clock, TrendingUp } from 'lucide-react';
import type { DailyGame, Sport } from '../../types';
import {TeamLogo} from '../ui/TeamLogo';

interface GameCardProps {
  game: DailyGame;
  index: number;
  isDark: boolean;
  onChat?: (message: string) => void;
}

const SPORT_EMOJI: Record<Sport, string> = {
  nba: '🏀',
  mlb: '⚾',
  soccer: '⚽',
};

const SPORT_BADGE: Record<Sport, string> = {
  nba: 'bg-orange-500/15 text-orange-500 dark:bg-orange-400/15 dark:text-orange-400',
  mlb: 'bg-red-500/15 text-red-600 dark:bg-red-400/15 dark:text-red-400',
  soccer: 'bg-emerald-500/15 text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-400',
};

export default function GameCard({ game, index, onChat }: GameCardProps) {
  const confidenceColor =
    game.confidence_pct >= 75
      ? 'text-emerald-500'
      : game.confidence_pct >= 55
      ? 'text-amber-500'
      : 'text-slate-400';

  const handleClick = () => {
    if (onChat) {
      onChat(`${game.home_team} vs ${game.away_team}`);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      onClick={handleClick}
      className="group cursor-pointer"
    >
      <div className="glass-card p-3 hover:border-brand-500/30 dark:hover:border-brand-400/30
                      transition-all duration-200 hover:shadow-md hover:shadow-brand-500/5">
        {/* Header: Sport + Time */}
        <div className="flex items-center justify-between mb-2">
          <span className={`px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded ${SPORT_BADGE[game.sport]}`}>
            {SPORT_EMOJI[game.sport]} {game.sport.toUpperCase()}
          </span>
          <span className="flex items-center gap-1 text-[10px] text-slate-400 dark:text-slate-500">
            <Clock className="w-2.5 h-2.5" />
            {game.start_time}
          </span>
        </div>

        {/* Matchup with Logos */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex flex-col items-center flex-1 text-center group-hover:transform group-hover:scale-105 transition-transform duration-300">
            <TeamLogo teamName={game.home_team} size="lg" className="mb-2" />
            <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-200 leading-tight group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">
              {game.home_team}
            </p>
          </div>
          <div className="flex flex-col items-center justify-center px-1">
            <span className="text-[10px] font-bold text-slate-300 dark:text-slate-600 bg-slate-100 dark:bg-white/5 px-2 py-1 rounded-full">VS</span>
          </div>
          <div className="flex flex-col items-center flex-1 text-center group-hover:transform group-hover:scale-105 transition-transform duration-300">
            <TeamLogo teamName={game.away_team} size="lg" className="mb-2" />
            <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-200 leading-tight group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">
              {game.away_team}
            </p>
          </div>
        </div>

        {/* Confidence + Pick */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-white/5">
          <div className="flex items-center gap-1">
            <TrendingUp className={`w-3 h-3 ${confidenceColor}`} />
            <span className={`text-[10px] font-bold ${confidenceColor}`}>
              {game.confidence_pct}%
            </span>
          </div>
          <span className="text-[10px] text-slate-400 dark:text-slate-500 truncate max-w-[60%]">
            {game.pick_value}
          </span>
        </div>
      </div>
    </motion.div>
  );
}
