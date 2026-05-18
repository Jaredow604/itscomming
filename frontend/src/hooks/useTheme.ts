import { useState, useEffect, useCallback } from 'react';
import type { Theme } from '../types';

/**
 * useTheme — Custom hook for dark/light mode management.
 *
 * Priority:
 *   1. localStorage (persisted user preference)
 *   2. prefers-color-scheme (OS default)
 *   3. 'dark' fallback (design default)
 *
 * Toggles the 'dark' class on <html> for Tailwind's darkMode: 'class'.
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    // 1. Check localStorage
    const stored = localStorage.getItem('itscoming-theme') as Theme | null;
    if (stored === 'dark' || stored === 'light') return stored;

    // 2. Check OS preference
    if (window.matchMedia('(prefers-color-scheme: light)').matches) {
      return 'light';
    }

    // 3. Default: dark
    return 'dark';
  });

  const isDark = theme === 'dark';

  // Apply theme class to <html>
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('itscoming-theme', theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  return { theme, isDark, toggleTheme };
}
