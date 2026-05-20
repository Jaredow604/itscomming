import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Flame,
  Snowflake,
  ChevronDown,
  ChevronUp,
  Filter,
  Target,
  BarChart3,
  Zap,
} from 'lucide-react';
import { LineChart, Line, ResponsiveContainer, YAxis, Tooltip } from 'recharts';
import apiClient from '../api/client';
import PlayerPhoto from '../components/ui/PlayerPhoto';
import TeamLogo from '../components/ui/TeamLogo';
import type { PlayerPropCard, PlayerPropMarket, PlayerPropsResponse } from '../types';

const SPORT_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  all: { label: 'Todos', icon: '🎯', color: 'from-violet-500 to-purple-600' },
  nba: { label: 'NBA', icon: '🏀', color: 'from-orange-500 to-red-600' },
  mlb: { label: 'MLB', icon: '⚾', color: 'from-blue-500 to-indigo-600' },
  soccer: { label: 'Soccer', icon: '⚽', color: 'from-emerald-500 to-green-600' },
};

const MARKET_LABELS: Record<string, string> = {
  Puntos: 'PTS',
  Rebotes: 'REB',
  Asistencias: 'AST',
  Triples: '3PM',
  'Pts+Reb+Ast': 'PRA',
  Hits: 'H',
  'Home Runs': 'HR',
  'Carreras Impulsadas': 'RBI',
  Ponches: 'K',
  Goles: 'GOL',
  'Tiros a Puerta': 'SOT',
  'Tiros Totales': 'SHOTS',
  'Goles+Asistencias': 'G+A',
};

const fetchPlayerProps = async (sport: string, minEv: number): Promise<PlayerPropsResponse> => {
  const params = new URLSearchParams();
  params.set('sport', sport);
  params.set('min_ev', String(minEv));
  const { data } = await apiClient.get(`/api/v1/player-props/?${params.toString()}`);
  return data;
};

function SparklineChart({ values, color }: { values: number[]; color: string }) {
  if (!values.length) return null;
  const data = values.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={40}>
      <LineChart data={data}>
        <YAxis hide domain={['dataMin - 1', 'dataMax + 1']} />
        <Tooltip
          content={({ active, payload }) =>
            active && payload?.[0] ? (
              <div className="bg-zinc-800 text-white text-xs px-2 py-1 rounded">
                {payload[0].value}
              </div>
            ) : null
          }
        />
        <Line
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function TrendBadge({ direction, strength }: { direction: string; strength: number }) {
  if (direction === 'up' && strength > 0.15) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full">
        <TrendingUp size={12} /> Trending Up
      </span>
    );
  }
  if (direction === 'down' && strength > 0.15) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full">
        <TrendingDown size={12} /> Trending Down
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-zinc-400 bg-zinc-400/10 px-2 py-0.5 rounded-full">
      <Minus size={12} /> Stable
    </span>
  );
}

function HotColdBadge({ hotCold }: { hotCold: string }) {
  if (hotCold === 'hot') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded-full">
        <Flame size={12} /> HOT
      </span>
    );
  }
  if (hotCold === 'cold') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-bold text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded-full">
        <Snowflake size={12} /> COLD
      </span>
    );
  }
  return null;
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const styles: Record<string, string> = {
    high: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
    medium: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
    lean: 'text-zinc-400 bg-zinc-400/10 border-zinc-400/20',
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${styles[confidence] || styles.lean}`}>
      {confidence.toUpperCase()}
    </span>
  );
}

function PropRow({ prop }: { prop: PlayerPropMarket }) {
  const isOver = prop.recommendation === 'OVER';
  const isNoBet = prop.recommendation === 'NO BET';

  return (
    <div className={`flex items-center justify-between px-3 py-2 rounded-lg transition-colors ${
      isNoBet ? 'bg-zinc-800/20' : isOver ? 'bg-emerald-400/5' : 'bg-red-400/5'
    }`}>
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-zinc-300 w-20">
          {MARKET_LABELS[prop.market] || prop.market}
        </span>
        <span className="text-sm text-zinc-500">Line</span>
        <span className="text-sm font-semibold text-white">{prop.line}</span>
      </div>
      <div className="flex items-center gap-4">
        <div className="text-right">
          <div className="text-xs text-zinc-500">Projected</div>
          <div className="text-sm font-semibold text-cyan-400">{prop.projected}</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-zinc-500">Over %</div>
          <div className="text-sm font-semibold text-white">{(prop.over_prob * 100).toFixed(0)}%</div>
        </div>
        <div className="text-right min-w-[60px]">
          <div className="text-xs text-zinc-500">EV</div>
          <div className={`text-sm font-bold ${prop.ev_pct > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {prop.ev_pct > 0 ? '+' : ''}{prop.ev_pct}%
          </div>
        </div>
        <ConfidenceBadge confidence={prop.confidence} />
        {!isNoBet && (
          <span className={`text-xs font-bold px-2 py-1 rounded ${
            isOver ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
          }`}>
            {prop.recommendation}
          </span>
        )}
      </div>
    </div>
  );
}

function PlayerCard({ player, isExpanded, onToggle }: {
  player: PlayerPropCard;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const sportConf = SPORT_CONFIG[player.sport] || SPORT_CONFIG.all;
  const trendColor = player.trends.trend_direction === 'up' ? '#34d399' :
                     player.trends.trend_direction === 'down' ? '#f87171' : '#a1a1aa';

  return (
    <div className="bg-zinc-900/50 backdrop-blur-sm border border-zinc-800/50 rounded-2xl overflow-hidden hover:border-zinc-700/50 transition-all duration-300">
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full p-5 flex items-start justify-between text-left"
      >
        <div className="flex items-start gap-4">
          <PlayerPhoto url={player.photo_url} name={player.player_name} sport={player.sport} className="w-14 h-14 rounded-xl flex-shrink-0" />
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white">{player.player_name}</h3>
              <HotColdBadge hotCold={player.trends.hot_cold} />
            </div>
            <div className="flex items-center gap-2 mt-1">
              <TeamLogo url={player.logo_url} name={player.team_name} className="w-4 h-4" />
              <span className="text-sm text-zinc-400">{player.team_name}</span>
              <span className="text-xs text-zinc-600">vs</span>
              <span className="text-sm text-zinc-300">{player.opponent}</span>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <TrendBadge direction={player.trends.trend_direction} strength={player.trends.trend_strength} />
              {player.trends.active_streak && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded-full">
                  <Zap size={10} /> {player.trends.active_streak}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          <div className={`text-xs font-bold px-2 py-1 rounded-full bg-gradient-to-r ${sportConf.color} text-white`}>
            {sportConf.icon} {sportConf.label}
          </div>
          <div className="text-right">
            <div className="text-xs text-zinc-500">Best EV</div>
            <div className={`text-xl font-black ${player.primary_ev > 0 ? 'text-emerald-400' : 'text-zinc-400'}`}>
              {player.primary_ev > 0 ? '+' : ''}{player.primary_ev}%
            </div>
          </div>
          <div className="text-zinc-500">
            {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </div>
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-5 pb-5 space-y-4 border-t border-zinc-800/50 pt-4">
          {/* Stats Summary */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-zinc-800/40 rounded-lg p-3 text-center">
              <div className="text-xs text-zinc-500">L5 Avg</div>
              <div className="text-lg font-bold text-white">{player.trends.l5_avg}</div>
            </div>
            <div className="bg-zinc-800/40 rounded-lg p-3 text-center">
              <div className="text-xs text-zinc-500">L10 Avg</div>
              <div className="text-lg font-bold text-white">{player.trends.l10_avg}</div>
            </div>
            <div className="bg-zinc-800/40 rounded-lg p-3 text-center">
              <div className="text-xs text-zinc-500">Season</div>
              <div className="text-lg font-bold text-white">{player.trends.season_avg}</div>
            </div>
          </div>

          {/* Home/Away + VS Opponent */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-zinc-800/30 rounded-lg p-2 text-center">
              <div className="text-xs text-zinc-500">Home</div>
              <div className="text-sm font-semibold text-zinc-300">{player.trends.home_avg}</div>
            </div>
            <div className="bg-zinc-800/30 rounded-lg p-2 text-center">
              <div className="text-xs text-zinc-500">Away</div>
              <div className="text-sm font-semibold text-zinc-300">{player.trends.away_avg}</div>
            </div>
            <div className="bg-zinc-800/30 rounded-lg p-2 text-center">
              <div className="text-xs text-zinc-500">vs Opp</div>
              <div className="text-sm font-semibold text-zinc-300">
                {player.trends.vs_opponent_avg !== null ? player.trends.vs_opponent_avg : 'N/A'}
              </div>
              {player.trends.vs_opponent_games > 0 && (
                <div className="text-xs text-zinc-600">({player.trends.vs_opponent_games} games)</div>
              )}
            </div>
          </div>

          {/* Sparkline */}
          {player.trends.last_10_values.length > 1 && (
            <div className="bg-zinc-800/30 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <BarChart3 size={14} className="text-zinc-500" />
                <span className="text-xs text-zinc-500">Last 10 Games</span>
              </div>
              <SparklineChart values={player.trends.last_10_values} color={trendColor} />
            </div>
          )}

          {/* Props List */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Target size={14} className="text-zinc-500" />
              <span className="text-sm font-semibold text-zinc-300">Prop Markets</span>
              <span className="text-xs text-zinc-600">({player.props.length} markets)</span>
            </div>
            <div className="space-y-1">
              {player.props.map((prop, idx) => (
                <PropRow key={idx} prop={prop} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PlayerPropsPage() {
  const [sport, setSport] = useState<string>('all');
  const [minEv, setMinEv] = useState<number>(0);
  const [showFilters, setShowFilters] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'ev' | 'confidence' | 'sport'>('ev');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['playerProps', sport, minEv],
    queryFn: () => fetchPlayerProps(sport, minEv),
    refetchOnWindowFocus: false,
  });

  const filteredProps = useMemo(() => {
    if (!data?.props) return [];
    let props = [...data.props];

    if (sortBy === 'confidence') {
      const order = { high: 3, medium: 2, lean: 1 };
      props.sort((a, b) => (order[b.primary_confidence] || 0) - (order[a.primary_confidence] || 0));
    } else if (sortBy === 'sport') {
      props.sort((a, b) => a.sport.localeCompare(b.sport));
    }

    return props;
  }, [data, sortBy]);

  return (
    <div className="min-h-screen bg-zinc-950 text-white p-4 pb-20 lg:p-8 lg:pl-[280px]">
      {/* Header */}
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl lg:text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-500">
              Player Props Analyzer
            </h1>
            <p className="text-zinc-400 mt-1 text-sm">
              AI-powered player props with trend analysis, pattern detection & real EV calculation.
            </p>
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-3 py-2 bg-zinc-800/50 rounded-lg hover:bg-zinc-700/50 transition-colors"
          >
            <Filter size={16} />
            <span className="text-sm text-zinc-300 hidden sm:inline">Filters</span>
          </button>
        </div>
      </header>

      {/* Summary Bar */}
      {data?.summary && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl p-4 text-center">
            <div className="text-2xl font-black text-white">{data.summary.total}</div>
            <div className="text-xs text-zinc-500 mt-1">Total Props Found</div>
          </div>
          <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl p-4 text-center">
            <div className="text-2xl font-black text-emerald-400">+{data.summary.avg_ev}%</div>
            <div className="text-xs text-zinc-500 mt-1">Average EV</div>
          </div>
          <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl p-4 text-center">
            <div className="text-2xl font-black text-cyan-400">{data.summary.high_confidence_count}</div>
            <div className="text-xs text-zinc-500 mt-1">High Confidence</div>
          </div>
        </div>
      )}

      {/* Sport Tabs */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-2">
        {Object.entries(SPORT_CONFIG).map(([key, conf]) => (
          <button
            key={key}
            onClick={() => setSport(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold whitespace-nowrap transition-all ${
              sport === key
                ? `bg-gradient-to-r ${conf.color} text-white shadow-lg`
                : 'bg-zinc-800/50 text-zinc-400 hover:bg-zinc-700/50 hover:text-white'
            }`}
          >
            <span>{conf.icon}</span>
            <span>{conf.label}</span>
          </button>
        ))}
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl p-4 mb-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">Min EV %</label>
              <input
                type="range"
                min="0"
                max="20"
                step="1"
                value={minEv}
                onChange={(e) => setMinEv(Number(e.target.value))}
                className="w-full accent-emerald-500"
              />
              <div className="text-sm text-zinc-300 text-center">+{minEv}%</div>
            </div>
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">Sort By</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as 'ev' | 'confidence' | 'sport')}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white"
              >
                <option value="ev">Best EV</option>
                <option value="confidence">Confidence</option>
                <option value="sport">Sport</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500"></div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 text-center text-red-400">
          <p>Unable to load Player Props. Please try again later.</p>
        </div>
      )}

      {/* No Results */}
      {!isLoading && filteredProps.length === 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center text-zinc-400">
          <p className="text-lg mb-2">No player props found</p>
          <p className="text-sm">Try lowering the minimum EV filter or check back later when games are scheduled.</p>
        </div>
      )}

      {/* Player Cards */}
      <div className="space-y-3">
        {filteredProps.map((player) => (
          <PlayerCard
            key={player.id}
            player={player}
            isExpanded={expandedId === player.id}
            onToggle={() => setExpandedId(expandedId === player.id ? null : player.id)}
          />
        ))}
      </div>
    </div>
  );
}
