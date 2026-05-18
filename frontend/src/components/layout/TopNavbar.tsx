import { Activity, BarChart3, MessageSquare, TrendingUp, TargetIcon } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import ThemeToggle from '../ThemeToggle';
import { useTheme } from '../../hooks/useTheme';
import type { Sport } from '../../types';

interface TopNavbarProps {
  activeSport: Sport | 'all';
  onSportChange: (sport: Sport | 'all') => void;
}

const LEAGUE_TABS = [
  { key: 'all' as const, label: 'All', icon: '🎯' },
  { key: 'soccer' as const, label: 'Soccer', icon: '⚽' },
  { key: 'nba' as const, label: 'NBA', icon: '🏀' },
  { key: 'mlb' as const, label: 'MLB', icon: '⚾' },
] as const;

export default function TopNavbar({ activeSport, onSportChange }: TopNavbarProps) {
  const { isDark, toggleTheme } = useTheme();
  const location = useLocation();
  const isDashboard = location.pathname === '/';
  const isStats = location.pathname === '/estadisticas';

  return (
    <header
      className="flex-shrink-0 flex items-center justify-between
                 px-4 sm:px-6 py-2.5
                 border-b border-slate-200/60 dark:border-white/10
                 bg-white/90 dark:bg-surface-900/90 backdrop-blur-xl
                 z-50"
    >
      {/* Left: Logo + Nav Links */}
      <div className="flex items-center gap-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 hover:opacity-80 transition-opacity">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-cyan-500
                          flex items-center justify-center shadow-md shadow-brand-500/20">
            <Activity className="w-4 h-4 text-white" />
          </div>
          <div className="hidden sm:block">
            <h1 className="text-sm font-bold text-slate-800 dark:text-white leading-none">
              It's Coming
            </h1>
            <p className="text-[9px] text-slate-400 dark:text-slate-500 font-medium tracking-wide">
              NEURAL SPORTS
            </p>
          </div>
        </Link>

        {/* Nav separator */}
        <div className="w-px h-6 bg-slate-200 dark:bg-white/10" />

        {/* Page Links */}
        <div className="flex items-center gap-1">
          <Link
            to="/"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                       transition-all duration-200
                       ${isDashboard
                         ? 'bg-brand-500/10 text-brand-600 dark:text-brand-400'
                         : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5'
                       }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Dashboard</span>
          </Link>

          <Link
            to="/estadisticas"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                       transition-all duration-200
                       ${isStats
                         ? 'bg-brand-500/10 text-brand-600 dark:text-brand-400'
                         : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5'
                       }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Estadísticas</span>
          </Link>
          <Link
            to="/player-props"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                       transition-all duration-200
                       ${location.pathname === '/player-props'
                         ? 'bg-brand-500/10 text-brand-600 dark:text-brand-400'
                         : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5'
                       }`}
          >
            <TargetIcon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Player Props</span>
          </Link>
        </div>
      </div>

      {/* Center: Sport Tabs (only on dashboard) */}
      {isDashboard && (
        <div className="hidden md:flex items-center gap-1 bg-slate-100 dark:bg-white/5 rounded-lg p-1">
          {LEAGUE_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => onSportChange(tab.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium
                         transition-all duration-200
                         ${activeSport === tab.key
                           ? 'bg-white dark:bg-surface-800 text-slate-800 dark:text-white shadow-sm'
                           : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
                         }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      )}
      
      {/* Right: Stats badge + Theme toggle */}
      <div className="flex items-center gap-2">
        {isStats && (
          <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 rounded-md
                         bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <TrendingUp className="w-3.5 h-3.5" />
            <span className="text-[10px] font-semibold">ANALYTICS</span>
          </div>
        )}
        <ThemeToggle isDark={isDark} onToggle={toggleTheme} />
      </div>
    </header>
  );
}
