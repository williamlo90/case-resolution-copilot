import { afterEach, describe, expect, it } from "vitest";
import {
  assertProviderAuthenticationConfigured,
  configuredAuthenticationMode,
  providerAuthenticationEnabled,
} from "./authentication";

const originalAuthMode = process.env.SUPPORT_COPILOT_AUTH_MODE;
const originalPublishableKey =
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
const originalSecretKey = process.env.CLERK_SECRET_KEY;

afterEach(() => {
  if (originalAuthMode === undefined) {
    delete process.env.SUPPORT_COPILOT_AUTH_MODE;
  } else {
    process.env.SUPPORT_COPILOT_AUTH_MODE = originalAuthMode;
  }
  if (originalPublishableKey === undefined) {
    delete process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  } else {
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY =
      originalPublishableKey;
  }
  if (originalSecretKey === undefined) {
    delete process.env.CLERK_SECRET_KEY;
  } else {
    process.env.CLERK_SECRET_KEY = originalSecretKey;
  }
});

describe("authentication configuration", () => {
  it("keeps deterministic development as the credential-free default", () => {
    delete process.env.SUPPORT_COPILOT_AUTH_MODE;

    expect(configuredAuthenticationMode()).toBe(
      "deterministic_development",
    );
    expect(providerAuthenticationEnabled()).toBe(false);
  });

  it("enables provider authentication explicitly", () => {
    process.env.SUPPORT_COPILOT_AUTH_MODE = "provider";

    expect(providerAuthenticationEnabled()).toBe(true);
  });

  it("requires explicit Clerk keys instead of keyless mode", () => {
    process.env.SUPPORT_COPILOT_AUTH_MODE = "provider";
    delete process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
    delete process.env.CLERK_SECRET_KEY;

    expect(() => assertProviderAuthenticationConfigured()).toThrow(
      "Provider authentication requires valid Clerk",
    );

    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "pk_placeholder";
    process.env.CLERK_SECRET_KEY = "sk_placeholder";
    expect(() => assertProviderAuthenticationConfigured()).not.toThrow();
  });

  it("rejects unsupported authentication modes", () => {
    process.env.SUPPORT_COPILOT_AUTH_MODE = "trusted_header";

    expect(() => configuredAuthenticationMode()).toThrow(
      "Unsupported authentication mode",
    );
  });
});
