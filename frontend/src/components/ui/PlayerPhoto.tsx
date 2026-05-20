import { useState, useMemo } from 'react';

interface PlayerPhotoProps {
  url?: string;
  name: string;
  className?: string;
  sport?: 'nba' | 'mlb' | 'soccer';
}

const ESPN_HEADSHOT_BASE = 'https://a.espncdn.com/i/headshots';

function buildEspnUrl(name: string, sport?: string): string | undefined {
  if (!name) return undefined;

  const sportKey = sport || 'nba';
  const nameParts = name.trim().toLowerCase().split(/\s+/);
  if (nameParts.length < 2) return undefined;

  const lastName = nameParts[nameParts.length - 1];
  const firstName = nameParts[0];

  return `${ESPN_HEADSHOT_BASE}/${sportKey}/players/full/${lastName}_${firstName}.png`;
}

export default function PlayerPhoto({ url, name, className = "w-16 h-16", sport }: PlayerPhotoProps) {
  const [fallbackPhase, setFallbackPhase] = useState<'none' | 'espn' | 'avatar'>('none');

  const espnUrl = useMemo(() => buildEspnUrl(name, sport), [name, sport]);

  const activeUrl = fallbackPhase === 'none'
    ? (url || espnUrl)
    : fallbackPhase === 'espn'
    ? espnUrl
    : undefined;

  const FallbackUser = () => (
    <div className={`${className} flex items-center justify-center bg-zinc-800 rounded-lg border border-zinc-700 overflow-hidden`} title={name}>
      <svg className="w-2/3 h-2/3 text-zinc-500 mt-2" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
      </svg>
    </div>
  );

  if (!activeUrl || fallbackPhase === 'avatar') {
    return <FallbackUser />;
  }

  return (
    <img
      src={activeUrl}
      alt={`${name} photo`}
      className={`${className} object-cover rounded-lg border border-zinc-700 shadow-md`}
      onError={() => {
        if (fallbackPhase === 'none' && url) {
          if (espnUrl) {
            setFallbackPhase('espn');
          } else {
            setFallbackPhase('avatar');
          }
        } else if (fallbackPhase === 'espn' || (fallbackPhase === 'none' && !url)) {
          setFallbackPhase('avatar');
        }
      }}
      title={name}
    />
  );
}
