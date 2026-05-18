import { useState } from 'react';
import TopNavbar from '../components/layout/TopNavbar';
import TodayGamesPanel from '../components/panels/TodayGamesPanel';
import BestPicksPanel from '../components/panels/BestPicksPanel';
import ChatLayout from '../components/chat/ChatLayout';
import { useTheme } from '../hooks/useTheme';
import type { Sport } from '../types';

export default function DashboardPage() {
  const { isDark } = useTheme();
  const [activeSport, setActiveSport] = useState<Sport | 'all'>('all');

  return (
    <div className="h-screen flex flex-col bg-surface-50 dark:bg-surface-950 transition-colors duration-300">
      {/* Top Navbar */}
      <TopNavbar activeSport={activeSport} onSportChange={setActiveSport} />

      {/* Main 3-column layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Today's Games (hidden on mobile) */}
        <aside className="hidden lg:flex flex-col w-72 xl:w-80 flex-shrink-0
                         border-r border-slate-200/60 dark:border-white/10
                         bg-slate-50/50 dark:bg-surface-900/50">
          <TodayGamesPanel sport={activeSport} isDark={isDark} />
        </aside>

        {/* Center: Chat */}
        <main className="flex-1 flex flex-col min-w-0">
          <ChatLayout />
        </main>

        {/* Right: Best Picks (hidden on tablet+) */}
        <aside className="hidden xl:flex flex-col w-72 flex-shrink-0
                         border-l border-slate-200/60 dark:border-white/10
                         bg-slate-50/50 dark:bg-surface-900/50">
          <BestPicksPanel />
        </aside>
      </div>
    </div>
  );
}
