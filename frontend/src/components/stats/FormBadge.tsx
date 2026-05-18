interface FormBadgeProps {
  result: string; // 'W', 'D', 'L'
}

export default function FormBadge({ result }: FormBadgeProps) {
  const colors =
    result === 'W'
      ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
      : result === 'D'
      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20'
      : 'bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/20';

  const labels: Record<string, string> = { W: 'W', D: 'D', L: 'L' };

  return (
    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-md text-[10px] font-bold ${colors}`}>
      {labels[result] || result}
    </span>
  );
}
