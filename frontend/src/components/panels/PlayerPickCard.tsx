import { motion } from 'framer-motion';
import { Flame, TrendingUp, TrendingDown, Snowflake, Target } from 'lucide-react';
import type { PlayerPropCard } from '../../types';
import PlayerPhoto from '../ui/PlayerPhoto';

interface PlayerPickCardProps {
  player: PlayerPropCard;
  index: number;
}

const SPORT_EMOJI: Record<string, string> = {
  nba: '🏀',
  mlb: '⚾',
  soccer: '⚽',
};

export default function PlayerPickCard({ player, index }: PlayerPickCardProps) {
  const bestProp = player.props[0];
  if (!bestProp) return null;

  const isOver = bestProp.recommendation === 'OVER';

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.08 }}
    >
      <div className="glass-card p-3 hover:shadow-md transition-shadow duration-200">
        {/* Header: Sport + Player */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm">{SPORT_EMOJI[player.sport]}</span>
          <PlayerPhoto
            url={player.photo_url}
            name={player.player_name}
            sport={player.sport}
            className="w-6 h-6 rounded-full"
          />
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-200 truncate">
              {player.player_name}
            </p>
            <p className="text-[9px] text-slate-400 truncate">
              {player.team_name} vs {player.opponent}
            </p>
          </div>
        </div>

        {/* Hot/Cold/Trend badges */}
        <div className="flex items-center gap-1 mb-2">
          {player.trends.hot_cold === 'hot' && (
            <span className="flex items-center gap-0.5 text-[9px] font-bold text-orange-500">
              <Flame className="w-2.5 h-2.5" /> HOT
            </span>
          )}
          {player.trends.hot_cold === 'cold' && (
            <span className="flex items-center gap-0.5 text-[9px] font-bold text-blue-500">
              <Snowflake className="w-2.5 h-2.5" /> COLD
            </span>
          )}
          {player.trends.trend_direction === 'up' && player.trends.trend_strength > 0.15 && (
            <span className="flex items-center gap-0.5 text-[9px] font-bold text-emerald-500">
              <TrendingUp className="w-2.5 h-2.5" /> UP
            </span>
          )}
          {player.trends.trend_direction === 'down' && player.trends.trend_strength > 0.15 && (
            <span className="flex items-center gap-0.5 text-[9px] font-bold text-red-500">
              <TrendingDown className="w-2.5 h-2.5" /> DOWN
            </span>
          )}
          {player.trends.active_streak && (
            <span className="text-[9px] text-amber-500 truncate ml-auto">
              🔥 {player.trends.active_streak.split(' ')[0]}
            </span>
          )}
        </div>

        {/* Best Prop */}
        <div className="flex items-center gap-1.5 mb-2">
          <Target className="w-3 h-3 text-brand-500" />
          <span className="text-[10px] font-bold text-brand-600 dark:text-brand-400">
            {bestProp.market} {isOver ? 'O' : 'U'} {bestProp.line}
          </span>
        </div>

        {/* Stats row */}
        <div className="flex items-center justify-between text-[9px] text-slate-400 mb-2">
          <span>Proj: <span className="text-slate-200 font-semibold">{bestProp.projected}</span></span>
          <span>Over: <span className="text-slate-200 font-semibold">{(bestProp.over_prob * 100).toFixed(0)}%</span></span>
        </div>

        {/* EV bar */}
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                bestProp.ev_pct > 5
                  ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
                  : bestProp.ev_pct > 0
                  ? 'bg-gradient-to-r from-blue-500 to-blue-400'
                  : 'bg-gradient-to-r from-slate-400 to-slate-300'
              }`}
              style={{ width: `${Math.min(Math.abs(bestProp.ev_pct) * 3, 100)}%` }}
            />
          </div>
          <span className={`text-[10px] font-mono font-bold min-w-[36px] text-right ${
            bestProp.ev_pct > 0 ? 'text-emerald-500' : 'text-slate-400'
          }`}>
            {bestProp.ev_pct > 0 ? '+' : ''}{bestProp.ev_pct}%
          </span>
        </div>

        {/* Confidence */}
        <div className="mt-1.5 flex justify-end">
          <span className={`text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${
            bestProp.confidence === 'high'
              ? 'bg-emerald-500/15 text-emerald-500'
              : bestProp.confidence === 'medium'
              ? 'bg-amber-500/15 text-amber-500'
              : 'bg-slate-500/15 text-slate-400'
          }`}>
            {bestProp.confidence}
          </span>
        </div>
      </div>
    </motion.div>
  );
}
