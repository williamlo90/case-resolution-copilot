import type { QualityDashboard } from "@/domain/quality/quality";

export interface QualityRepository {
  readonly source: "api" | "mock";
  getDashboard(): Promise<QualityDashboard>;
}
