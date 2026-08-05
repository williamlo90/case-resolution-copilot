export type AuthenticationMode =
  | "deterministic_development"
  | "provider";

export function configuredAuthenticationMode(): AuthenticationMode {
  const value =
    process.env.SUPPORT_COPILOT_AUTH_MODE ?? "deterministic_development";
  if (value === "deterministic_development" || value === "provider") {
    return value;
  }
  throw new Error(`Unsupported authentication mode: ${value}`);
}

export function providerAuthenticationEnabled(): boolean {
  return configuredAuthenticationMode() === "provider";
}

export function assertProviderAuthenticationConfigured(): void {
  if (!providerAuthenticationEnabled()) {
    return;
  }
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const secretKey = process.env.CLERK_SECRET_KEY;
  if (!publishableKey?.startsWith("pk_") || !secretKey?.startsWith("sk_")) {
    throw new Error(
      "Provider authentication requires valid Clerk publishable and secret keys.",
    );
  }
}
