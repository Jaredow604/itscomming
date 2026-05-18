import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import type { DailyGame } from '../types';

export function useTodayGames(sport?: string) {
  return useQuery<DailyGame[]>({
    queryKey: ['today-games', sport],
    queryFn: async () => {
      const params = sport ? { sport } : {};
      const { data } = await apiClient.get('/api/v1/today/', { params });
      return data.games || [];
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
