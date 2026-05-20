/* ==========================================
   TypeScript Interfaces — It's Coming Platform
   ========================================== */

/** Prediction confidence metrics */
export interface PredictionConfidence {
  spread_std: number;
  total_std: number;
}

/** MLB dispersion metrics */
export interface MLBDispersion {
  alpha_home: number;
  alpha_away: number;
}

/** NBA prediction payload */
export interface NBAPrediction {
  spread: number;
  total: number;
  favored: 'home' | 'away' | 'even';
  confidence: PredictionConfidence;
}

/** MLB prediction payload */
export interface MLBPrediction {
  projected_runs_home: number;
  projected_runs_away: number;
  total_runs: number;
  favored: 'home' | 'away' | 'even';
  dispersion: MLBDispersion;
}

/** Elo trend data for the last N games */
export interface EloTrend {
  home: number[];
  away: number[];
  labels: string[];
}

/** Single H2H stat comparison */
export interface H2HStat {
  stat: string;
  home: number;
  away: number;
}

/** Soccer prediction payload */
export interface SoccerPrediction {
  probabilities: { home: number; draw: number; away: number };
  favored: 'home' | 'draw' | 'away';
}

/** Alternative line for a specific market */
export interface AltLine {
  line: number;
  over_prob: number;
  under_prob: number;
}

/** Alternative lines market (cards, corners, SOT) */
export interface AltLineMarket {
  line: number;
  over_prob: number;
  under_prob: number;
  expected: number;
  alt_lines: AltLine[];
}

/** All alternative lines payload */
export interface AltLinesPayload {
  cards: AltLineMarket;
  corners: AltLineMarket;
  shots_on_target: AltLineMarket;
}

/** Player prop prediction */
export interface PlayerProp {
  player: string;
  team: string;
  prop: string;
  line: number;
  over_prob: number;
  under_prob: number;
  ev: string;
}

/** Widget data payload embedded in bot response */
export interface WidgetPayload {
  sport: 'nba' | 'mlb' | 'soccer';
  home_team: string;
  away_team: string;
  start_time: string;
  prediction: NBAPrediction | MLBPrediction | SoccerPrediction;
  alt_lines?: AltLinesPayload;
  player_props?: PlayerProp[];
  elo_trend: EloTrend;
  h2h_stats: H2HStat[];
}

/** Chat message */
export interface ChatMessage {
  id: string;
  role: 'user' | 'bot';
  content: string;
  widget?: WidgetPayload;
  timestamp: Date;
}

/** API request body */
export interface ChatRequest {
  message: string;
}

/** API response body */
export interface ChatResponse {
  reply: string;
  widget?: WidgetPayload;
}

/** Theme type */
export type Theme = 'dark' | 'light';

/** Sport type for consistency */
export type Sport = 'nba' | 'mlb' | 'soccer';

/** Daily game from the schedule */
export interface DailyGame {
  id?: number;
  sport: Sport;
  home_team: string;
  away_team: string;
  home_logo_url?: string;
  away_logo_url?: string;
  start_time: string;
  prediction: NBAPrediction | MLBPrediction | SoccerPrediction;
  confidence_pct: number;
  xg_home?: number | null;
  xg_away?: number | null;
  pick_type: string;
  pick_value: string;
  pick_reason: string;
}

/** Pick record (today or history) */
export interface PickRecord {
  sport: Sport;
  home_team: string;
  away_team: string;
  home_logo_url?: string;
  away_logo_url?: string;
  start_time?: string;
  pick_type: string;
  pick_value: string;
  confidence_pct: number;
  edge: string;
  reason?: string;
  result?: 'win' | 'loss' | 'pending';
  actual_score?: string;
  date: string;
}

/** Picks API response */
export interface PicksResponse {
  today: PickRecord[];
  history: PickRecord[];
  record: { wins: number; losses: number; total: number; win_rate: number };
}

/** Team stats from API */
export interface TeamStatsEntry {
  name: string;
  logo_url?: string;
  prom_goles: number;
  prom_tiros_puerta: number;
  prom_corners: number;
}

/** Team detail with match info */
export interface TeamDetail {
  name: string;
  logo_url?: string;
  prom_goles: number;
  prom_tiros_puerta: number;
  prom_corners: number;
  match_today?: {
    opponent: string;
    home_away: 'home' | 'away';
    start_time: string;
    full_match: string;
  };
}

/** Team comparison response */
export interface TeamComparison {
  teams: TeamStatsEntry[];
  advantages: string[];
}

/** Stats API response */
export interface StatsResponse {
  teams: TeamStatsEntry[];
  detail?: TeamDetail;
  comparison?: TeamComparison;
}

/** League config for UI */
export interface LeagueConfig {
  key: string;
  label: string;
  sport: Sport | 'all';
  icon: string;
}

/** Standing entry for a league table */
export interface LeagueStanding {
  team_id: number;
  team_name: string;
  logo_url: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  goal_diff: number;
  points: number;
}

/** Standings API response */
export interface StandingsResponse {
  standings: LeagueStanding[];
  league: string;
  season?: string;
  available_seasons?: string[];
}

/** Player prop market (single betting line) */
export interface PlayerPropMarket {
  market: string;
  line: number;
  casino_odds: number;
  projected: number;
  over_prob: number;
  under_prob: number;
  ev_pct: number;
  recommendation: 'OVER' | 'UNDER' | 'NO BET';
  confidence: 'high' | 'medium' | 'lean';
}

/** Player trend analytics */
export interface PlayerTrends {
  l5_avg: number;
  l10_avg: number;
  season_avg: number;
  trend_direction: 'up' | 'down' | 'flat';
  trend_strength: number;
  home_avg: number;
  away_avg: number;
  vs_opponent_avg: number | null;
  vs_opponent_games: number;
  active_streak: string | null;
  hot_cold: 'hot' | 'cold' | 'neutral';
  last_10_values: number[];
}

/** Full player prop card with all analytics */
export interface PlayerPropCard {
  id: string;
  sport: Sport;
  player_name: string;
  team_name: string;
  opponent: string;
  game_time: string;
  photo_url?: string;
  logo_url?: string;
  props: PlayerPropMarket[];
  trends: PlayerTrends;
  primary_ev: number;
  primary_confidence: 'high' | 'medium' | 'lean';
}

/** Player Props API response */
export interface PlayerPropsResponse {
  props: PlayerPropCard[];
  summary: {
    total: number;
    avg_ev: number;
    high_confidence_count: number;
  };
}
