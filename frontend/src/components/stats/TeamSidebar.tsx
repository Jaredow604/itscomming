import { useState, useMemo } from 'react';
import { Search, Target, X, Plus } from 'lucide-react';
import { Loader2 } from 'lucide-react';
import type { TeamStatsEntry } from '../../types';
import TeamLogo from '../ui/TeamLogo';

interface TeamSidebarProps {
  teams: TeamStatsEntry[];
  isLoading: boolean;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  selectedTeam: string | null;
  onSelectTeam: (name: string) => void;
  compareMode: boolean;
  onToggleCompare: () => void;
  compareTeam: string | null;
}

// Simple heuristic to map teams to leagues for the filter
const LEAGUE_KEYWORDS = {
  'Premier League': ['Arsenal', 'Chelsea', 'Manchester', 'Liverpool', 'Tottenham', 'Everton', 'Villa', 'Newcastle', 'West Ham', 'Brighton', 'Fulham', 'Brentford', 'Palace', 'Nottingham', 'Wolves', 'Bournemouth', 'Burnley', 'Sheffield', 'Luton'],
  'La Liga': ['Madrid', 'Barcelona', 'Sevilla', 'Villarreal', 'Valencia', 'Osasuna', 'Betis', 'Celta', 'Sociedad', 'Bilbao', 'Getafe', 'Rayo', 'Mallorca', 'Alav', 'Girona', 'Granada', 'Las Palmas', 'Cadiz', 'Almeria', 'Espanyol', 'Levante', 'Elche', 'Oviedo'],
  'Serie A': ['Roma', 'Fiorentina', 'Juventus', 'Milan', 'Napoli', 'Lazio', 'Atalanta', 'Bologna', 'Torino', 'Cagliari', 'Genoa', 'Parma', 'Udinese', 'Verona', 'Sassuolo', 'Empoli', 'Lecce', 'Frosinone', 'Salernitana', 'Monza'],
  'NBA': ['Lakers', 'Celtics', 'Warriors', 'Bulls', 'Heat', 'Knicks', 'Nuggets', 'Mavericks', 'Suns', 'Bucks', '76ers', 'Clippers', 'Timberwolves', 'Thunder', 'Spurs', 'Kings', 'Pelicans', 'Rockets', 'Pacers', 'Cavaliers', 'Magic', 'Hawks', 'Raptors', 'Grizzlies', 'Jazz', 'Nets', 'Hornets', 'Pistons', 'Wizards', 'Trail Blazers'],
  'MLB': ['Yankees', 'Dodgers', 'Red Sox', 'Cubs', 'Braves', 'Astros', 'Phillies', 'Rangers', 'Orioles', 'Rays', 'Blue Jays', 'Twins', 'Guardians', 'White Sox', 'Tigers', 'Royals', 'Mariners', 'Angels', 'Athletics', 'Mets', 'Marlins', 'Nationals', 'Brewers', 'Cardinals', 'Reds', 'Pirates', 'Diamondbacks', 'Padres', 'Giants', 'Rockies']
};

const getLeagueForTeam = (teamName: string) => {
  for (const [league, keywords] of Object.entries(LEAGUE_KEYWORDS)) {
    if (keywords.some(k => teamName.toLowerCase().includes(k.toLowerCase()))) {
      return league;
    }
  }
  return 'Otras';
};

export default function TeamSidebar({
  teams,
  isLoading,
  searchQuery,
  onSearchChange,
  selectedTeam,
  onSelectTeam,
  compareMode,
  onToggleCompare,
  compareTeam,
}: TeamSidebarProps) {
  const [activeLeague, setActiveLeague] = useState<string>('Todas');

  const filteredTeams = useMemo(() => {
    if (activeLeague === 'Todas') return teams;
    return teams.filter(t => getLeagueForTeam(t.name) === activeLeague);
  }, [teams, activeLeague]);

  const availableLeagues = useMemo(() => {
    const leagues = new Set<string>();
    teams.forEach(t => leagues.add(getLeagueForTeam(t.name)));
    return ['Todas', ...Array.from(leagues).sort()];
  }, [teams]);

  const uniqueTeams = useMemo(() => {
    const seen = new Map<string, TeamStatsEntry>();
    filteredTeams.forEach(t => {
      const existing = seen.get(t.name);
      if (!existing || (t.logo_url && !existing.logo_url)) {
        seen.set(t.name, t);
      }
    });
    return Array.from(seen.values());
  }, [filteredTeams]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200/60 dark:border-white/10">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold text-slate-800 dark:text-white">Equipos</h2>
          <button
            onClick={onToggleCompare}
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-semibold
                       transition-all duration-200
                       ${compareMode
                         ? 'bg-brand-500/15 text-brand-600 dark:text-brand-400'
                         : 'bg-slate-100 dark:bg-white/5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
                       }`}
          >
            {compareMode ? (
              <>
                <X className="w-3 h-3" />
                Cancelar
              </>
            ) : (
              <>
                <Plus className="w-3 h-3" />
                Comparar
              </>
            )}
          </button>
        </div>

        {/* League Filter */}
        <div className="mb-2 overflow-x-auto pb-1 scrollbar-hide flex gap-1">
          {availableLeagues.map(league => (
            <button
              key={league}
              onClick={() => setActiveLeague(league)}
              className={`whitespace-nowrap px-2.5 py-1 rounded-full text-[10px] font-bold transition-colors
                ${activeLeague === league 
                  ? 'bg-slate-800 text-white dark:bg-white dark:text-slate-900' 
                  : 'bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-white/5 dark:text-slate-400 dark:hover:bg-white/10'}`}
            >
              {league}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Buscar equipo..."
            className="w-full pl-8 pr-3 py-2 rounded-lg
                       bg-slate-100 dark:bg-white/5
                       border border-slate-200/60 dark:border-white/10
                       text-xs text-slate-700 dark:text-slate-200
                       placeholder:text-slate-400 dark:placeholder:text-slate-500
                       focus:outline-none focus:ring-1 focus:ring-brand-500/40"
          />
        </div>
      </div>

      {/* Team list */}
      <div className="flex-1 overflow-y-auto py-2">
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-4 h-4 text-brand-500 animate-spin" />
          </div>
        )}

        {!isLoading && uniqueTeams.length === 0 && (
          <div className="text-center py-8">
            <p className="text-xs text-slate-400">Sin equipos</p>
          </div>
        )}

        {uniqueTeams.map((team) => {
          const isSelected = selectedTeam === team.name;
          const isCompared = compareTeam === team.name;

          return (
            <button
              key={team.name}
              onClick={() => onSelectTeam(team.name)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-left
                         transition-all duration-150
                         ${isSelected
                           ? 'bg-brand-500/10 border-l-2 border-brand-500'
                           : isCompared
                           ? 'bg-amber-500/10 border-l-2 border-amber-500'
                           : 'hover:bg-slate-100/80 dark:hover:bg-white/5 border-l-2 border-transparent'
                         }`}
            >
              <TeamLogo url={team.logo_url} name={team.name} size="sm" className="flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className={`text-xs font-medium truncate
                  ${isSelected ? 'text-brand-600 dark:text-brand-400' : 'text-slate-700 dark:text-slate-200'}`}>
                  {team.name}
                </p>
                {team.prom_goles > 0 && (
                  <p className="text-[10px] text-slate-400 dark:text-slate-500">
                    {team.prom_goles.toFixed(2)} g/game
                  </p>
                )}
              </div>
              {isCompared && (
                <Target className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
