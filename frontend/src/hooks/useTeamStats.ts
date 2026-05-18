import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import type { StatsResponse } from '../types';

interface UseTeamStatsOptions {
  sport?: string;
  team?: string;
  compare?: string;
  matchToday?: boolean;
}

export function useTeamStats(options?: UseTeamStatsOptions) {
  return useQuery<StatsResponse>({
    queryKey: ['team-stats', options],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (options?.sport) params.sport = options.sport;
      if (options?.team) params.team = options.team;
      if (options?.compare) params.compare = options.compare;
      if (options?.matchToday) params.match_today = 'true';

      const { data } = await apiClient.get('/api/v1/stats/', { params });
      return data;
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
