"use client";

import { useCallback, useEffect, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "theme";

// Also injected inline in app/layout.tsx <head> so the correct theme
// applies before first paint — without that, a saved "dark" preference
// would flash the light default for a frame on every load.
export const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem("${STORAGE_KEY}");
    if (stored === "light" || stored === "dark") {
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (e) {}
})();
`;

function applyTheme(preference: ThemePreference) {
  if (preference === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", preference);
  }
}

export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>("system");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") {
      setPreference(stored);
    }
  }, []);

  const setTheme = useCallback((next: ThemePreference) => {
    setPreference(next);
    applyTheme(next);
    if (next === "system") {
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      window.localStorage.setItem(STORAGE_KEY, next);
    }
  }, []);

  const cycleTheme = useCallback(() => {
    setTheme(preference === "light" ? "dark" : preference === "dark" ? "system" : "light");
  }, [preference, setTheme]);

  return { preference, setTheme, cycleTheme };
}
