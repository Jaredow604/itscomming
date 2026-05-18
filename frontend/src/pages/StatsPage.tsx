import { useState, useMemo } from 'react';
import TopNavbar from '../components/layout/TopNavbar';
import TeamSidebar from '../components/stats/TeamSidebar';
import TeamDetailPanel from '../components/stats/TeamDetailPanel';
import TeamComparison from '../components/stats/TeamComparison';
import { useTeamStats } from '../hooks/useTeamStats';
import { useTheme } from '../hooks/useTheme';
import type { Sport } from '../types';

export default function StatsPage() {
  const { isDark } = useTheme();
  const [activeSport, setActiveSport] = useState<Sport | 'all'>('all');
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

      {/* Main 2-column layout */}
      <div className="flex-1 flex overflow-hidden">
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
                  Ver métricas, forma reciente y enfrentamientos
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
