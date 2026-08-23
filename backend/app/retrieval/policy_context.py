from typing import TypedDict

from app.domain.cases import CaseWorkspaceRecord


class CaseRetrievalContext(TypedDict):
    category: str
    products: set[str]
    region: str
    channel: str
    tier: str


def case_context(workspace: CaseWorkspaceRecord) -> CaseRetrievalContext:
    products = {
        str(context.fields["product"]).strip().lower()
        for context in workspace.business_contexts
        if context.fields.get("product")
    }
    locale_parts = workspace.customer.locale.replace("_", "-").split("-")
    return {
        "category": workspace.case.category.value,
        "products": products or {"unknown"},
        "region": locale_parts[-1].lower() if len(locale_parts) > 1 else "unknown",
        "channel": workspace.request.channel.value,
        "tier": workspace.customer.tier.value,
    }


def context_label(context: CaseRetrievalContext, decision_scope: str) -> str:
    products = ", ".join(sorted(context["products"]))
    return (
        f"{decision_scope}; category {context['category']}; products {products}; "
        f"region {context['region']}; channel {context['channel']}; tier {context['tier']}"
    )
