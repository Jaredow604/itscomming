import React from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import PlayerPhoto from '../components/ui/PlayerPhoto';
import TeamLogo from '../components/ui/TeamLogo';

interface PlayerProp {
  id: number | string;
  player_name: string;
  team_name: string;
  prop_type: string;
  ev_score: number;
  prediction_value: string;
  photo_url?: string;
  logo_url?: string;
}

const fetchPlayerProps = async (): Promise<PlayerProp[]> => {
  const { data } = await apiClient.get('/api/v1/player-props/');
  return data;
};

export default function PlayerPropsPage() {
  const { data: propsList, isLoading, isError } = useQuery({
    queryKey: ['playerProps'],
    queryFn: fetchPlayerProps,
  });

  return (
    <div className="min-h-screen bg-zinc-950 text-white p-6 pb-20 lg:p-10 lg:pl-[280px]">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-500">
          Player Props EV
        </h1>
        <p className="text-zinc-400 mt-2">
          Top Props of the day calculated with our Deep Learning Engine and Expected Value (Z-Score).
        </p>
      </header>

      {isLoading && (
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500"></div>
        </div>
      )}

      {isError && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 text-center text-red-400">
          <p>Unable to load Player Props at this time. Please try again later.</p>
        </div>
      )}

      {propsList && propsList.length === 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center text-zinc-400">
          <p>No profitable Player Props found for today.</p>
        </div>
      )}

      {propsList && propsList.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {propsList.map((prop, idx) => (
            <div 
              key={prop.id || idx} 
              className="bg-zinc-900/40 backdrop-blur-sm border border-zinc-800/50 rounded-2xl p-6 hover:bg-zinc-800/50 transition-colors duration-300 flex flex-col relative overflow-hidden"
            >
              {/* Neon accent based on EV */}
              <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 blur-3xl rounded-full transform translate-x-1/2 -translate-y-1/2"></div>
              
              <div className="flex items-start justify-between mb-4 relative z-10">
                <div className="flex items-center gap-4">
                  <PlayerPhoto url={prop.photo_url} name={prop.player_name} className="w-16 h-16 rounded-xl" />
                  <div>
                    <h3 className="text-lg font-bold text-white">{prop.player_name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <TeamLogo url={prop.logo_url} name={prop.team_name} className="w-5 h-5" />
                      <span className="text-sm text-zinc-400">{prop.team_name}</span>
                    </div>
                  </div>
                </div>
                
                <div className="flex flex-col items-end">
                  <span className="text-xs text-zinc-500 uppercase tracking-wider mb-1">EV Score</span>
                  <span className="text-xl font-black text-emerald-400">{prop.ev_score}</span>
                </div>
              </div>

              <div className="mt-auto pt-4 border-t border-zinc-800/50 relative z-10">
                <div className="flex justify-between items-center bg-zinc-950/50 rounded-lg p-3">
                  <div className="flex flex-col">
                    <span className="text-xs text-zinc-500 uppercase tracking-wider">Prop</span>
                    <span className="font-semibold text-white">{prop.prop_type}</span>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="text-xs text-zinc-500 uppercase tracking-wider">Hit %</span>
                    <span className="font-semibold text-cyan-400">{prop.prediction_value}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}