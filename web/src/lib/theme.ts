/**
 * Client-only theme store, read via useSyncExternalStore.
 *
 *   layout.tsx no-flash script   →  sets initial <html class="dark"> pre-paint
 *   ThemeToggle (setDarkTheme)    →  the only writer afterward
 *   useSyncExternalStore subs     →  re-render on change, no setState-in-effect
 *
 * Light is the default; dark is opt-in and persisted under `strata-theme`.
 */

const STORAGE_KEY = "strata-theme";

type Listener = () => void;
const listeners = new Set<Listener>();

export function subscribeTheme(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

// Reads the live <html> class the no-flash script (or a prior toggle) set.
export function isDarkSnapshot(): boolean {
  return document.documentElement.classList.contains("dark");
}

// The DOM isn't readable during SSR / the hydration render — assume the light
// default so server and first client render agree.
export function isDarkServerSnapshot(): boolean {
  return false;
}

export function setDarkTheme(dark: boolean): void {
  const root = document.documentElement;
  root.classList.toggle("dark", dark);
  root.style.colorScheme = dark ? "dark" : "light";
  try {
    localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
  } catch {
    // Private mode / blocked storage: the toggle still works for this session.
  }
  for (const listener of listeners) listener();
}
