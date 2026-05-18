import React, { useState } from 'react';

interface TeamLogoProps {
  url?: string;
  name: string;
  className?: string;
}

export default function TeamLogo({ url, name, className = "w-10 h-10" }: TeamLogoProps) {
  const [error, setError] = useState(false);

  // SVG Fallback Shield
  const FallbackShield = () => (
    <div className={`${className} flex items-center justify-center bg-zinc-800 rounded-full border border-zinc-700`} title={name}>
      <svg className="w-1/2 h-1/2 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    </div>
  );

  if (!url || error) {
    return <FallbackShield />;
  }

  return (
    <img
      src={url}
      alt={`${name} logo`}
      className={`${className} object-contain`}
      onError={() => setError(true)}
      title={name}
    />
  );
}