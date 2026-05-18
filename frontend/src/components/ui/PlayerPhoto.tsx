import React, { useState } from 'react';

interface PlayerPhotoProps {
  url?: string;
  name: string;
  className?: string;
}

export default function PlayerPhoto({ url, name, className = "w-16 h-16" }: PlayerPhotoProps) {
  const [error, setError] = useState(false);

  // SVG Fallback User Silhouette
  const FallbackUser = () => (
    <div className={`${className} flex items-center justify-center bg-zinc-800 rounded-lg border border-zinc-700 overflow-hidden`} title={name}>
      <svg className="w-2/3 h-2/3 text-zinc-500 mt-2" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
      </svg>
    </div>
  );

  if (!url || error) {
    return <FallbackUser />;
  }

  return (
    <img 
      src={url} 
      alt={`${name} photo`} 
      className={`${className} object-cover rounded-lg border border-zinc-700 shadow-md`}
      onError={() => setError(true)}
      title={name}
    />
  );
}