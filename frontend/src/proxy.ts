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
import { retiredWorkspaceDestination } from "@/config/retired-workspace-links";

const attachClerkContext = clerkMiddleware({
  contentSecurityPolicy: {
    strict: true,
    directives: CLERK_CSP_DIRECTIVES,
  },
});

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  const destination = retiredWorkspaceDestination(request.nextUrl);
  if (destination) return NextResponse.redirect(destination);
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
