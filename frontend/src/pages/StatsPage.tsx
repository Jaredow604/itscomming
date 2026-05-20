import { useState, useMemo } from 'react';
import TopNavbar from '../components/layout/TopNavbar';
import TeamSidebar from '../components/stats/TeamSidebar';
import TeamDetailPanel from '../components/stats/TeamDetailPanel';
import TeamComparison from '../components/stats/TeamComparison';
import LeagueStandings from '../components/stats/LeagueStandings';
import { useTeamStats } from '../hooks/useTeamStats';
import { useTheme } from '../hooks/useTheme';
import type { Sport } from '../types';

type SubTab = 'equipos' | 'tabla';

export default function StatsPage() {
  const { isDark } = useTheme();
  const [activeSport, setActiveSport] = useState<Sport | 'all'>('all');
  const [activeSubTab, setActiveSubTab] = useState<SubTab>('equipos');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [compareTeam, setCompareTeam] = useState<string | null>(null);

  // Fetch all teams
  const { data: statsData, isLoading } = useTeamStats({ sport: activeSport === 'all' ? undefined : activeSport });

  // Filter teams by search
  const filteredTeams = useMemo(() => {
    if (!statsData?.teams) return [];
    let teams = statsData.teams;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      teams = teams.filter((t: { name: string }) => t.name.toLowerCase().includes(q));
    }
    return teams;
  }, [statsData?.teams, searchQuery]);

  // Fetch detail when team selected
  const { data: detailData } = useTeamStats({ team: selectedTeam || undefined });

  // Fetch comparison data
  const { data: comparisonData } = useTeamStats({
    compare: (selectedTeam && compareTeam) ? `${selectedTeam},${compareTeam}` : undefined,
  });

  const sportForNav: Sport | 'all' = activeSport;

  return (
    <div className="h-screen flex flex-col bg-surface-50 dark:bg-surface-950 transition-colors duration-300">
      {/* Top Navbar */}
      <TopNavbar activeSport={sportForNav} onSportChange={(s) => { setActiveSport(s); setSelectedTeam(null); setCompareMode(false); }} />

      {/* Sub-tabs */}
      <div className="flex-shrink-0 flex items-center gap-1 px-4 py-2 border-b border-slate-200/60 dark:border-white/10
                      bg-white/60 dark:bg-surface-900/60 backdrop-blur-sm">
        <button
          onClick={() => setActiveSubTab('equipos')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200
            ${activeSubTab === 'equipos'
              ? 'bg-brand-500/10 text-brand-600 dark:text-brand-400'
              : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5'}`}
        >
          Equipos
        </button>
        <button
          onClick={() => setActiveSubTab('tabla')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200
            ${activeSubTab === 'tabla'
              ? 'bg-brand-500/10 text-brand-600 dark:text-brand-400'
              : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5'}`}
        >
          Tabla
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {activeSubTab === 'tabla' ? (
          <LeagueStandings isDark={isDark} />
        ) : (
          <>
            {/* Left: Team Sidebar */}
            <aside className="flex flex-col w-64 xl:w-72 flex-shrink-0
                             border-r border-slate-200/60 dark:border-white/10
                             bg-slate-50/50 dark:bg-surface-900/50">
              <TeamSidebar
                teams={filteredTeams}
                isLoading={isLoading}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                selectedTeam={selectedTeam}
                onSelectTeam={(name: string) => {
                  if (compareMode && selectedTeam && !compareTeam) {
                    setCompareTeam(name);
                  } else {
                    setSelectedTeam(name);
                    setCompareTeam(null);
                  }
                }}
                compareMode={compareMode}
                onToggleCompare={() => {
                  setCompareMode(!compareMode);
                  setCompareTeam(null);
                }}
                compareTeam={compareTeam}
              />
            </aside>

            {/* Right: Detail Panel */}
            <main className="flex-1 overflow-y-auto">
              {compareMode && selectedTeam && compareTeam && comparisonData?.comparison ? (
                <TeamComparison
                  comparison={comparisonData.comparison}
                  onClose={() => { setCompareMode(false); setCompareTeam(null); }}
                  onChat={(msg) => {
                    window.location.href = `/?chat=${encodeURIComponent(msg)}`;
                  }}
                />
              ) : detailData?.detail ? (
                <TeamDetailPanel
                  detail={detailData.detail}
                  teams={statsData?.teams || []}
                  isDark={isDark}
                  compareMode={compareMode}
                  onCompare={() => setCompareMode(true)}
                  onChat={(msg) => {
                    window.location.href = `/?chat=${encodeURIComponent(msg)}`;
                  }}
                />
              ) : (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <p className="text-lg font-bold text-slate-300 dark:text-slate-600">
                      Selecciona un equipo
                    </p>
                    <p className="text-xs text-slate-400 dark:text-slate-600 mt-1">
                      Ver metricas, forma reciente y enfrentamientos
                    </p>
                  </div>
                </div>
              )}
            </main>
          </>
        )}
      </div>
    </div>
  );
}
