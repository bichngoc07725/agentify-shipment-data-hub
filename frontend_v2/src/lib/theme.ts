const KEY = 'agentify-theme';

export type ThemeMode = 'light' | 'dark';

export function getStoredTheme(): ThemeMode {
  return (localStorage.getItem(KEY) as ThemeMode) || 'light';
}

export function applyTheme(mode: ThemeMode) {
  document.documentElement.setAttribute('data-theme', mode);
  localStorage.setItem(KEY, mode);
}
