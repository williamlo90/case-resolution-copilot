export type DataSource = "api" | "mock";

export function configuredDataSource(): DataSource {
  return process.env.SUPPORT_COPILOT_DATA_MODE === "mock" ? "mock" : "api";
}
