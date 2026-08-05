import { clerkMiddleware } from "@clerk/nextjs/server";
import {
  NextResponse,
  type NextFetchEvent,
  type NextRequest,
} from "next/server";
import {
  assertProviderAuthenticationConfigured,
  providerAuthenticationEnabled,
} from "@/config/authentication";
import { CLERK_CSP_DIRECTIVES } from "@/config/security-headers";

const attachClerkContext = clerkMiddleware({
  contentSecurityPolicy: {
    strict: true,
    directives: CLERK_CSP_DIRECTIVES,
  },
});

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  if (!providerAuthenticationEnabled()) {
    return NextResponse.next();
  }
  assertProviderAuthenticationConfigured();
  return attachClerkContext(request, event);
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
    "/__clerk/(.*)",
  ],
};
