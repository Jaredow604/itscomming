import { motion } from 'framer-motion';
import { CheckCircle2, XCircle, Target } from 'lucide-react';
import type { PickRecord, Sport } from '../../types';
import TeamLogo from '../ui/TeamLogo';

interface PickCardProps {
  pick: PickRecord;
  index: number;
  isHistorical: boolean;
}

const SPORT_EMOJI: Record<Sport, string> = {
  nba: '🏀',
  mlb: '⚾',
  soccer: '⚽',
};

const EDGE_BADGE: Record<string, string> = {
  Sharp: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20',
  Value: 'bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/20',
  Moderate: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20',
  Lean: 'bg-slate-500/15 text-slate-500 dark:text-slate-400 border border-slate-500/20',
};

const CONFIDENCE_BAR_COLORS = [
  'from-emerald-500 to-emerald-400',
  'from-blue-500 to-blue-400',
  'from-amber-500 to-amber-400',
  'from-slate-400 to-slate-300',
];

export default function PickCard({ pick, index, isHistorical }: PickCardProps) {
  const barColorIndex =
    pick.confidence_pct >= 75 ? 0 :
    pick.confidence_pct >= 60 ? 1 :
    pick.confidence_pct >= 50 ? 2 : 3;

  const barColor = CONFIDENCE_BAR_COLORS[barColorIndex];

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.08 }}
    >
      <div className="glass-card p-3 hover:shadow-md transition-shadow duration-200">
        {/* Header: Sport + Date/Time + Result */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm">{SPORT_EMOJI[pick.sport]}</span>

          <div className="flex items-center gap-1">
            {isHistorical ? (
              <>
                {pick.result === 'win' ? (
                  <span className="flex items-center gap-0.5 text-[10px] font-bold text-emerald-500">
                    <CheckCircle2 className="w-3 h-3" /> WIN
                  </span>
                ) : (
                  <span className="flex items-center gap-0.5 text-[10px] font-bold text-red-500">
                    <XCircle className="w-3 h-3" /> LOSS
                  </span>
                )}
              </>
            ) : (
              <span className={`px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded ${EDGE_BADGE[pick.edge] || EDGE_BADGE.Lean}`}>
                {pick.edge}
              </span>
            )}
          </div>
        </div>

        {/* Matchup */}
        <div className="flex items-center gap-1.5 mb-2">
          <TeamLogo url={pick.home_logo_url} name={pick.home_team} size="sm" />
          <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-200 truncate">
            {pick.home_team}
          </p>
          <span className="text-[9px] text-slate-400 mx-0.5">vs</span>
          <TeamLogo url={pick.away_logo_url} name={pick.away_team} size="sm" />
          <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-200 truncate">
            {pick.away_team}
          </p>
        </div>

        {/* Pick Value */}
        <div className="flex items-center gap-1.5 mb-2">
          <Target className="w-3 h-3 text-brand-500" />
          <span className="text-xs font-bold text-brand-600 dark:text-brand-400">
            {pick.pick_value}
          </span>
        </div>

        {/* Confidence bar */}
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden">
            <div
              className={`h-full bg-gradient-to-r ${barColor} rounded-full transition-all duration-500`}
              style={{ width: `${pick.confidence_pct}%` }}
            />
          </div>
          <span className="text-[10px] font-mono font-bold text-slate-500 dark:text-slate-400 min-w-[30px] text-right">
            {pick.confidence_pct}%
          </span>
        </div>

        {/* Score (historical only) */}
        {isHistorical && pick.actual_score && (
          <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1.5 font-mono">
            Score: {pick.actual_score}
          </p>
        )}

        {/* Reason (today only) */}
        {!isHistorical && pick.reason && (
          <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1.5 line-clamp-1">
            {pick.reason}
          </p>
        )}
      </div>
    </motion.div>
  );
}
