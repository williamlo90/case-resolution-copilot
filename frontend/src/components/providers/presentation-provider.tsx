"use client";

import {
  createContext,
  type ReactNode,
  useContext,
  useMemo,
} from "react";

export type PresentationPreferences = {
  locale: string;
  timeZone: string;
};

const fallbackPreferences: PresentationPreferences = {
  locale: "en-US",
  timeZone: "UTC",
};

const PresentationContext =
  createContext<PresentationPreferences>(fallbackPreferences);

function supportedPreferences(
  locale: string,
  timeZone: string,
): PresentationPreferences {
  try {
    new Intl.DateTimeFormat(locale, { timeZone }).format();
    return { locale, timeZone };
  } catch {
    return fallbackPreferences;
  }
}

export function PresentationProvider({
  children,
  locale,
  timeZone,
}: PresentationPreferences & { children: ReactNode }) {
  const value = useMemo(
    () => supportedPreferences(locale, timeZone),
    [locale, timeZone],
  );
  return (
    <PresentationContext.Provider value={value}>
      {children}
    </PresentationContext.Provider>
  );
}

export function usePresentationPreferences(): PresentationPreferences {
  return useContext(PresentationContext);
}
