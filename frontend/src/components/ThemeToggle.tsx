import { Sun, Moon } from 'lucide-react';
import { motion } from 'framer-motion';

interface ThemeToggleProps {
  isDark: boolean;
  onToggle: () => void;
}

/**
 * ThemeToggle — Animated sun/moon button for switching between dark and light mode.
 *
 * Uses Framer Motion for a smooth rotation + scale animation on toggle.
 * The icon swaps between Sun (light mode) and Moon (dark mode).
 */
export default function ThemeToggle({ isDark, onToggle }: ThemeToggleProps) {
  return (
    <button
      onClick={onToggle}
      className="relative p-2.5 rounded-xl
                 bg-slate-100 dark:bg-white/10
                 hover:bg-slate-200 dark:hover:bg-white/20
                 border border-slate-200/60 dark:border-white/10
                 transition-all duration-300 ease-out
                 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Modo Claro' : 'Modo Oscuro'}
    >
      <motion.div
        key={isDark ? 'moon' : 'sun'}
        initial={{ scale: 0, rotate: -90, opacity: 0 }}
        animate={{ scale: 1, rotate: 0, opacity: 1 }}
        exit={{ scale: 0, rotate: 90, opacity: 0 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
      >
        {isDark ? (
          <Moon className="w-[18px] h-[18px] text-amber-400" />
        ) : (
          <Sun className="w-[18px] h-[18px] text-amber-500" />
        )}
      </motion.div>
    </button>
  );
}
