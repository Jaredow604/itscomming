import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import type { PicksResponse } from '../types';

export function useBestPicks() {
  return useQuery<PicksResponse>({
    queryKey: ['best-picks'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/v1/picks/');
      return data;
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
