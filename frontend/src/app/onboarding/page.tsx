import { providerAuthenticationEnabled } from "@/config/authentication";
import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import { ApiClientError } from "@/data/api/api-client";
import { getCaseRepository } from "@/data/cases/case-repository-provider";
import { getPolicyRepository } from "@/data/policies/policy-repository-provider";
import { getReviewRepository } from "@/data/reviews/review-repository-provider";
import { OnboardingPage } from "@/features/access/components/onboarding-page";
import { buildOnboardingSteps } from "@/features/access/onboarding-readiness";
import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = { title: "Workspace setup" };
export const dynamic = "force-dynamic";

async function onboardingData() {
  const administration = getAdministrationRepository();
  const cases = getCaseRepository();
  const policies = getPolicyRepository();
  const reviews = getReviewRepository();
  const [
    context,
    generalSettings,
    approvalSettings,
    members,
    connections,
    caseList,
    policyList,
    reviewList,
  ] =
    await Promise.all([
      administration.getSessionContext(),
      administration.getSettings("general"),
      administration.getSettings("approvals"),
      administration.listMembers(),
      administration.listConnections(),
      cases.listCases(),
      policies.listPolicies(),
      reviews.listReviews(),
    ]);
  const testWorkspace = caseList.items[0]
    ? await cases.getCaseWorkspace(caseList.items[0].id)
    : null;
  const activeMembers = members.filter((member) => member.status === "active");
  const hasReviewer = activeMembers.some(
    (member) =>
      member.role === "supervisor" || member.role === "administrator",
  );
  const publishedPolicies = policyList.filter(
    (policy) => policy.status === "published",
  );
  const usableConnections = connections.filter(
    (connection) =>
      ["connected", "demo"].includes(connection.credentialStatus) &&
      connection.health === "healthy",
  );
  const hasLiveCaseSource = usableConnections.some(
    (connection) => connection.providerType === "case_source",
  );
  const hasActionTarget = usableConnections.some(
    (connection) => connection.capabilities.write.length > 0,
  );
  const hasApprovalRule =
    approvalSettings.section === "approvals" &&
    approvalSettings.configuration.requireDecisionReason &&
    Object.keys(
      approvalSettings.configuration.administratorFinancialLimits,
    ).length > 0;
  return {
    steps: buildOnboardingSteps({
      workspaceConfigured:
        generalSettings.section === "general" &&
        Boolean(
          generalSettings.configuration.organizationName.trim() &&
            generalSettings.configuration.locale.trim() &&
            generalSettings.configuration.timeZone.trim(),
        ),
      hasOperatingTeam: activeMembers.length >= 2 && hasReviewer,
      hasPublishedPolicy: publishedPolicies.length > 0,
      hasCaseSource: hasLiveCaseSource || caseList.total > 0,
      hasActionTarget,
      hasApprovalRule,
      hasConfigurationTest:
        reviewList.length > 0 || Boolean(testWorkspace?.proposal),
    }),
    summary: {
      organizationName:
        generalSettings.section === "general"
          ? generalSettings.configuration.organizationName
          : context.organization.name,
      caseCount: caseList.total,
      publishedPolicyCount: publishedPolicies.length,
      activeMemberCount: activeMembers.length,
      connectedToolCount: usableConnections.length,
    },
  };
}

export default async function OnboardingRoute() {
  let data;
  try {
    data = await onboardingData();
  } catch (error) {
    if (
      providerAuthenticationEnabled() &&
      error instanceof ApiClientError
    ) {
      if (error.status === 401) redirect("/sign-in");
      if (error.status === 403) redirect("/access-denied");
      if (error.code === "workspace_access_denied") redirect("/access-denied");
      if (error.code === "workspace_selection_required") {
        redirect("/workspace-selection");
      }
    }
    throw error;
  }
  return <OnboardingPage steps={data.steps} summary={data.summary} />;
}
