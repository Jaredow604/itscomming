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

/** Widget data payload embedded in bot response */
export interface WidgetPayload {
  sport: 'nba' | 'mlb' | 'soccer';
  home_team: string;
  away_team: string;
  start_time: string;
  prediction: NBAPrediction | MLBPrediction | SoccerPrediction;
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
  prom_goles: number;
  prom_tiros_puerta: number;
  prom_corners: number;
}

/** Team detail with match info */
export interface TeamDetail {
  name: string;
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
