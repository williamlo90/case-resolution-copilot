export function practiceHref(href: string, session: string | null): string {
  if (!session || !/^VD-[A-F0-9]{16}$/.test(session) || !/^\/(cases|reviews|actions|policies)(\/|\?|$)/.test(href)) return href;
  const url = new URL(href, "https://workspace.invalid");
  url.searchParams.set("practice", session);
  return url.pathname + url.search + url.hash;
}
