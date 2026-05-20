import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import type { PlayerPropsResponse } from '../types';

export function usePlayerProps(sport: string = 'all', minEv: number = 0) {
  return useQuery<PlayerPropsResponse>({
    queryKey: ['player-props', sport, minEv],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set('sport', sport);
      params.set('min_ev', String(minEv));
      const { data } = await apiClient.get(`/api/v1/player-props/?${params.toString()}`);
      return data;
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
