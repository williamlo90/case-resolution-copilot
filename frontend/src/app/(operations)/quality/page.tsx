import { getQualityRepository } from "@/data/quality/quality-repository-provider";
import { QualityDashboard } from "@/features/quality/components/quality-dashboard";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Quality" };
export const dynamic = "force-dynamic";

export default async function QualityPage() {
  const dashboard = await getQualityRepository().getDashboard();
  return <QualityDashboard dashboard={dashboard} />;
}
