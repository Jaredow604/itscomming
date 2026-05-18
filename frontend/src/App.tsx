import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import StatsPage from './pages/StatsPage';
import PlayerPropsPage from './pages/PlayerPropsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    mutations: {
      retry: 1,
    },
    queries: {
      refetchOnWindowFocus: false,
    },
  },
});

/**
 * App — Root component with React Router + React Query provider.
 *
 * Routes:
 *   /              → Dashboard (3-column: games, chat, picks)
 *   /estadisticas  → Stats page (team analytics, comparison)
 *   /player-props  → Player Props page (EV, headshots)
 */
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/estadisticas" element={<StatsPage />} />
          <Route path="/player-props" element={<PlayerPropsPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}