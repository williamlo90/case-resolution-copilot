"use server";

import { ApiClientError } from "@/data/api/api-client";
import { apiInboxDraftRepository } from "@/data/connections/api-inbox-draft-repository";
import type { InboxDraftDelivery } from "@/domain/connections/connected-inbox";
import type { InboxDraftState } from "@/features/connections/action-contracts";
import { revalidatePath } from "next/cache";
import { commandFailure, commandSuccess, commandWarning } from "./shared";

function deliveryState(delivery: InboxDraftDelivery): InboxDraftState {
  if (delivery.status === "completed") {
    return {
      ...commandSuccess("Gmail draft created. Nothing was sent automatically."),
      delivery,
    };
  }
  if (delivery.status === "outcome_unknown") {
    return {
      ...commandWarning(
        "We could not confirm whether Gmail created the draft. Check its status before trying again.",
      ),
      delivery,
    };
  }
  if (delivery.status === "failed_safe") {
    return {
      ...commandFailure(
        new ApiClientError(
          "No Gmail draft was created. Review the connection and try again.",
          409,
          delivery.lastErrorCode ?? "inbox_draft_failed_safe",
          "unavailable",
        ),
      ),
      delivery,
    };
  }
  if (delivery.status === "recovery_required") {
    return {
      ...commandFailure(
        new ApiClientError(
          "Sign in to the connected inbox again before checking this draft.",
          409,
          delivery.lastErrorCode ?? "inbox_draft_recovery_required",
          "unavailable",
        ),
      ),
      delivery,
    };
  }
  return {
    ...commandWarning("Gmail is still preparing the draft. Check again shortly."),
    delivery,
  };
}

export async function deliverResponseDraft(
  caseId: string,
  expectedDraftVersion: number,
  _previousState: InboxDraftState,
  _formData: FormData,
): Promise<InboxDraftState> {
  void _formData;
  try {
    const delivery = await apiInboxDraftRepository.deliver(
      caseId,
      expectedDraftVersion,
    );
    revalidatePath(`/cases/${caseId}`);
    return deliveryState(delivery);
  } catch (error) {
    return { ...commandFailure(error), delivery: _previousState.delivery };
  }
}

export async function reconcileResponseDraft(
  _previousState: InboxDraftState,
  formData: FormData,
): Promise<InboxDraftState> {
  const deliveryId = String(formData.get("delivery_id") ?? "");
  if (!deliveryId) {
    return {
      ...commandFailure(
        new ApiClientError(
          "The draft status reference is missing. Refresh this case.",
          422,
          "draft_delivery_id_missing",
          "unavailable",
        ),
      ),
      delivery: _previousState.delivery,
    };
  }
  try {
    return deliveryState(
      await apiInboxDraftRepository.reconcile(deliveryId),
    );
  } catch (error) {
    return { ...commandFailure(error), delivery: _previousState.delivery };
  }
}
