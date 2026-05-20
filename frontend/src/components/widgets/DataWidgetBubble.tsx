import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Trophy,
  TrendingUp,
  Clock,
  Zap,
  Target,
  Shield,
  Footprints,
  Crosshair,
} from 'lucide-react';
import EloTrendChart from './EloTrendChart';
import H2HStatsChart from './H2HStatsChart';
import type { WidgetPayload, NBAPrediction, MLBPrediction, SoccerPrediction, AltLinesPayload, PlayerProp } from '../../types';

interface DataWidgetBubbleProps {
  widget: WidgetPayload;
  isDark: boolean;
}

type TabId = 'prediction' | 'altlines' | 'playerprops';

export default function DataWidgetBubble({ widget, isDark }: DataWidgetBubbleProps) {
  const [activeTab, setActiveTab] = useState<TabId>('prediction');

  const isNBA = widget.sport === 'nba';
  const isMLB = widget.sport === 'mlb';
  const isSoccer = widget.sport === 'soccer';
  const prediction = widget.prediction;

  const hasAltLines = isSoccer && widget.alt_lines && Object.keys(widget.alt_lines).length > 0;
  const hasPlayerProps = widget.player_props && widget.player_props.length > 0;

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'prediction', label: 'Prediccion', icon: <Zap className="w-3 h-3" /> },
    ...(hasAltLines ? [{ id: 'altlines' as TabId, label: 'Alt Lines', icon: <Target className="w-3 h-3" /> }] : []),
    ...(hasPlayerProps ? [{ id: 'playerprops' as TabId, label: 'Player Props', icon: <Crosshair className="w-3 h-3" /> }] : []),
  ];

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
          <div className="flex items-center gap-2 mb-3">
            <span
              className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest rounded-md
                ${isNBA
                  ? 'bg-orange-500/15 text-orange-500 dark:bg-orange-400/15 dark:text-orange-400'
                  : isMLB
                    ? 'bg-blue-500/15 text-blue-500 dark:bg-blue-400/15 dark:text-blue-400'
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

        {/* ====== TABS ====== */}
        {tabs.length > 1 && (
          <div className="px-5 pb-3">
            <div className="flex gap-1 bg-slate-100/80 dark:bg-white/5 rounded-lg p-1">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all
                    ${activeTab === tab.id
                      ? 'bg-white dark:bg-white/10 text-slate-800 dark:text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
                    }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ====== PREDICTION METRICS ====== */}
        <div className="px-5 pb-4">
          <div className="flex items-center gap-1.5 mb-3">
            <Zap className="w-3.5 h-3.5 text-brand-500" />
            <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              {activeTab === 'prediction' ? 'Neural Prediction' : activeTab === 'altlines' ? 'Alternative Lines' : 'Player Props'}
            </p>
          </div>

          {activeTab === 'prediction' && (
            isNBA ? (
              <NBAMetrics prediction={prediction as NBAPrediction} />
            ) : isMLB ? (
              <MLBMetrics prediction={prediction as MLBPrediction} />
            ) : (
              <SoccerMetrics prediction={prediction as SoccerPrediction} />
            )
          )}

          {activeTab === 'altlines' && hasAltLines && (
            <AltLinesSection altLines={widget.alt_lines!} />
          )}

          {activeTab === 'playerprops' && hasPlayerProps && (
            <PlayerPropsSection props={widget.player_props!} />
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
              Powered by PyTorch Neural Networks &bull; Poisson Distribution &bull; Elo + Pythagorean Expectation
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
        label="Visitante"
        value={`${(prediction.probabilities.away * 100).toFixed(0)}%`}
        highlight={prediction.favored === 'away'}
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

/* ==========================================
   ALT LINES SECTION
   ========================================== */

function AltLinesSection({ altLines }: { altLines: AltLinesPayload }) {
  const markets: { key: keyof AltLinesPayload; label: string; icon: React.ReactNode }[] = [
    { key: 'cards', label: 'Tarjetas', icon: <Shield className="w-3.5 h-3.5" /> },
    { key: 'corners', label: 'Corners', icon: <Footprints className="w-3.5 h-3.5" /> },
    { key: 'shots_on_target', label: 'Tiros a Puerta', icon: <Crosshair className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="space-y-3">
      {markets.map(m => {
        const market = altLines[m.key];
        if (!market) return null;
        return (
          <div key={m.key}>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-slate-400 dark:text-slate-500">{m.icon}</span>
              <span className="text-[11px] font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                {m.label}
              </span>
              <span className="text-[10px] text-slate-400 dark:text-slate-500 ml-auto">
                Exp: {market.expected}
              </span>
            </div>

            {/* Main line */}
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-xs font-bold text-slate-700 dark:text-slate-200 w-12">
                O/U {market.line}
              </span>
              <div className="flex-1 flex h-5 rounded-md overflow-hidden bg-slate-100 dark:bg-white/5">
                <div
                  className="bg-emerald-500/80 dark:bg-emerald-400/70 flex items-center justify-center text-[9px] font-bold text-white transition-all"
                  style={{ width: `${market.over_prob * 100}%` }}
                >
                  {market.over_prob > 0.2 ? `${(market.over_prob * 100).toFixed(0)}%` : ''}
                </div>
                <div
                  className="bg-red-500/60 dark:bg-red-400/50 flex items-center justify-center text-[9px] font-bold text-white transition-all"
                  style={{ width: `${market.under_prob * 100}%` }}
                >
                  {market.under_prob > 0.2 ? `${(market.under_prob * 100).toFixed(0)}%` : ''}
                </div>
              </div>
            </div>

            {/* Alt lines */}
            {market.alt_lines.length > 0 && (
              <div className="flex gap-1.5 ml-14">
                {market.alt_lines.map((alt, i) => (
                  <AltLineBadge key={i} line={alt.line} overProb={alt.over_prob} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function AltLineBadge({ line, overProb }: { line: number; overProb: number }) {
  const isValue = Math.abs(overProb - 0.5) < 0.1;
  return (
    <span
      className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold
        ${isValue
          ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30'
          : 'bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 border border-slate-200/40 dark:border-white/5'
        }`}
    >
      {line} O{(overProb * 100).toFixed(0)}
    </span>
  );
}

/* ==========================================
   PLAYER PROPS SECTION
   ========================================== */

function PlayerPropsSection({ props }: { props: PlayerProp[] }) {
  if (props.length === 0) return null;

  return (
    <div className="space-y-1.5">
      {props.map((prop, i) => {
        const evNum = parseFloat(prop.ev.replace('%', ''));
        const isPositive = evNum > 0;
        return (
          <div
            key={i}
            className="flex items-center gap-3 px-3 py-2 rounded-lg
                       bg-slate-50 dark:bg-white/5 border border-slate-200/40 dark:border-white/5"
          >
            <div className="flex-1 min-w-0">
              <p className="text-[11px] font-bold text-slate-700 dark:text-slate-200 truncate">
                {prop.player}
              </p>
              <p className="text-[9px] text-slate-400 dark:text-slate-500">
                {prop.prop} O/U {prop.line}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex h-4 w-16 rounded overflow-hidden bg-slate-100 dark:bg-white/5">
                <div
                  className="bg-emerald-500/70 dark:bg-emerald-400/60 transition-all"
                  style={{ width: `${prop.over_prob * 100}%` }}
                />
                <div
                  className="bg-red-500/50 dark:bg-red-400/40 transition-all"
                  style={{ width: `${prop.under_prob * 100}%` }}
                />
              </div>
              <span
                className={`text-[10px] font-bold px-1.5 py-0.5 rounded
                  ${isPositive
                    ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                    : 'bg-red-500/15 text-red-500 dark:text-red-400'
                  }`}
              >
                {prop.ev}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
