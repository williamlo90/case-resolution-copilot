"use client";
import { createContext, useContext } from "react";
export const PracticeContext = createContext<string | null>(null);
export function usePracticeSession() { return useContext(PracticeContext); }
