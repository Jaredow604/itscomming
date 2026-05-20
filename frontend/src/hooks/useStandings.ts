import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import type { StandingsResponse } from '../types';

export function useStandings(league: string, season?: string) {
  return useQuery({
    queryKey: ['standings', league, season],
    queryFn: async (): Promise<StandingsResponse> => {
      const { data } = await apiClient.get<StandingsResponse>('/api/v1/standings/', {
        params: { league, season: season || undefined },
      });
      return data;
    },
    enabled: !!league,
    retry: 1,
  });
}
