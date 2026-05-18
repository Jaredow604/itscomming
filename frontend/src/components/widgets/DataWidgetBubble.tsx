import { motion } from 'framer-motion';
import {
  Trophy,
  TrendingUp,
  Clock,
  Zap,
} from 'lucide-react';
import EloTrendChart from './EloTrendChart';
import H2HStatsChart from './H2HStatsChart';
import type { WidgetPayload, NBAPrediction, MLBPrediction, SoccerPrediction } from '../../types';

interface DataWidgetBubbleProps {
  widget: WidgetPayload;
  isDark: boolean;
}

/**
 * DataWidgetBubble — Premium prediction card embedded inside a bot message.
 *
 * Renders structured prediction data with two embedded Recharts:
 *   - EloTrendChart: Elo evolution (last 5 games)
 *   - H2HStatsChart: Radar comparison of key metrics
 *
 * Fully adapts to dark/light theme via Tailwind classes.
 */
export default function DataWidgetBubble({ widget, isDark }: DataWidgetBubbleProps) {
  const isNBA = widget.sport === 'nba';
  const isMLB = widget.sport === 'mlb';
  const prediction = widget.prediction;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="w-full max-w-lg mt-2"
    >
      <div className="glass-card overflow-hidden">
        {/* ====== HEADER ====== */}
        <div className="relative px-5 pt-5 pb-4">
          {/* Sport badge */}
          <div className="flex items-center gap-2 mb-3">
            <span
              className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest rounded-md
                ${isNBA
                  ? 'bg-orange-500/15 text-orange-500 dark:bg-orange-400/15 dark:text-orange-400'
                  : 'bg-red-500/15 text-red-600 dark:bg-red-400/15 dark:text-red-400'
                }`}
            >
              {widget.sport.toUpperCase()}
            </span>
            <span className="flex items-center gap-1 text-[11px] text-slate-400">
              <Clock className="w-3 h-3" />
              {widget.start_time}
            </span>
          </div>

          {/* Matchup */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex-1 text-center">
              <p className="text-base font-bold text-slate-800 dark:text-white leading-tight">
                {widget.home_team}
              </p>
              <p className="text-[10px] text-slate-400 mt-0.5 uppercase tracking-wider">
                Local
              </p>
            </div>

            <div className="flex-shrink-0 flex flex-col items-center">
              <span className="text-xs font-semibold text-slate-400 dark:text-slate-500">
                VS
              </span>
            </div>

            <div className="flex-1 text-center">
              <p className="text-base font-bold text-slate-800 dark:text-white leading-tight">
                {widget.away_team}
              </p>
              <p className="text-[10px] text-slate-400 mt-0.5 uppercase tracking-wider">
                Visitante
              </p>
            </div>
          </div>
        </div>

        {/* ====== PREDICTION METRICS ====== */}
        <div className="px-5 pb-4">
          <div className="flex items-center gap-1.5 mb-3">
            <Zap className="w-3.5 h-3.5 text-brand-500" />
            <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Neural Prediction
            </p>
          </div>

          {isNBA ? (
            <NBAMetrics prediction={prediction as NBAPrediction} />
          ) : isMLB ? (
            <MLBMetrics prediction={prediction as MLBPrediction} />
          ) : (
            <SoccerMetrics prediction={prediction as SoccerPrediction} />
          )}
        </div>

        {/* ====== DIVIDER ====== */}
        <div className="mx-5 border-t border-slate-200/60 dark:border-white/10" />

        {/* ====== CHARTS ====== */}
        <div className="px-5 py-4 space-y-4">
          <EloTrendChart
            data={widget.elo_trend}
            homeTeam={widget.home_team}
            awayTeam={widget.away_team}
            isDark={isDark}
          />

          <div className="border-t border-slate-200/40 dark:border-white/5" />

          <H2HStatsChart
            data={widget.h2h_stats}
            homeTeam={widget.home_team}
            awayTeam={widget.away_team}
            isDark={isDark}
          />
        </div>

        {/* ====== FOOTER ====== */}
        <div className="px-5 py-3 bg-slate-50/80 dark:bg-white/[0.02]
                        border-t border-slate-200/60 dark:border-white/5">
          <div className="flex items-center gap-1.5">
            <Trophy className="w-3 h-3 text-amber-500" />
            <p className="text-[10px] text-slate-400 dark:text-slate-500">
              Powered by PyTorch Neural Networks &bull; Elo + Pythagorean Expectation
            </p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* ==========================================
   SUB-COMPONENTS: Sport-specific metrics
   ========================================== */

function NBAMetrics({ prediction }: { prediction: NBAPrediction }) {
  const favoredLabel =
    prediction.favored === 'home' ? 'Local' :
    prediction.favored === 'away' ? 'Visitante' : 'Parejo';

  const conf = prediction.confidence ?? { spread_std: 0, total_std: 0 };

  return (
    <div className="grid grid-cols-3 gap-2">
      <MetricCard
        label="Spread"
        value={prediction.spread > 0 ? `+${prediction.spread}` : `${prediction.spread}`}
        sub={`\u00b1${conf.spread_std}`}
        highlight={prediction.favored !== 'even'}
      />
      <MetricCard
        label="Total O/U"
        value={`${prediction.total}`}
        sub={`\u00b1${conf.total_std}`}
      />
      <MetricCard
        label="Favorecido"
        value={favoredLabel}
        icon={<TrendingUp className="w-3.5 h-3.5" />}
        highlight
      />
    </div>
  );
}

function SoccerMetrics({ prediction }: { prediction: SoccerPrediction }) {
  const favoredLabel =
    prediction.favored === 'home' ? 'Local' :
    prediction.favored === 'away' ? 'Visitante' : 'Empate';

  return (
    <div className="grid grid-cols-3 gap-2">
      <MetricCard
        label="Local"
        value={`${(prediction.probabilities.home * 100).toFixed(0)}%`}
        highlight={prediction.favored === 'home'}
      />
      <MetricCard
        label="Empate"
        value={`${(prediction.probabilities.draw * 100).toFixed(0)}%`}
        highlight={prediction.favored === 'draw'}
      />
      <MetricCard
        label="Favorecido"
        value={favoredLabel}
        icon={<TrendingUp className="w-3.5 h-3.5" />}
        highlight
      />
    </div>
  );
}

function MLBMetrics({ prediction }: { prediction: MLBPrediction }) {
  const favoredLabel =
    prediction.favored === 'home' ? 'Local' :
    prediction.favored === 'away' ? 'Visitante' : 'Parejo';

  const disp = prediction.dispersion ?? { alpha_home: 0, alpha_away: 0 };

  return (
    <div className="grid grid-cols-3 gap-2">
      <MetricCard
        label="Runs Local"
        value={`${prediction.projected_runs_home}`}
        sub={`\u03b1=${disp.alpha_home}`}
      />
      <MetricCard
        label="Runs Visit"
        value={`${prediction.projected_runs_away}`}
        sub={`\u03b1=${disp.alpha_away}`}
      />
      <MetricCard
        label="Favorecido"
        value={favoredLabel}
        icon={<TrendingUp className="w-3.5 h-3.5" />}
        highlight
      />
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  icon,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl px-3 py-2.5 text-center transition-colors
        ${highlight
          ? 'bg-brand-500/10 dark:bg-brand-400/10 border border-brand-500/20 dark:border-brand-400/20'
          : 'bg-slate-100/80 dark:bg-white/5 border border-slate-200/40 dark:border-white/5'
        }`}
    >
      <p className="text-[10px] text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
        {label}
      </p>
      <div className="flex items-center justify-center gap-1">
        {icon}
        <p
          className={`text-lg font-bold leading-none
            ${highlight ? 'text-brand-600 dark:text-brand-400' : 'text-slate-800 dark:text-white'}`}
        >
          {value}
        </p>
      </div>
      {sub && (
        <p className="text-[9px] text-slate-400 dark:text-slate-500 mt-1 font-mono">
          {sub}
        </p>
      )}
    </div>
  );
}
