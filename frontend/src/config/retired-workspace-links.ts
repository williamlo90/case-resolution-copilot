/** Old practice bookmarks return to the ordinary queue without keeping their session query. */
export function retiredWorkspaceDestination(input: Pick<URL, "pathname" | "searchParams" | "origin">): URL | null {
  const demo = input.pathname === "/demo/v2" || input.pathname.startsWith("/demo/v2/");
  const practice = input.searchParams.has("practice") &&
    /^\/(cases|reviews|actions|policies)(\/|$)/.test(input.pathname);
  return demo || practice ? new URL("/cases", input.origin) : null;
}
