from app.domain.policies import (
    ParsedPolicyClause,
    PolicyApplicability,
    PolicySourceParseError,
)

GOVERNED_CORPUS_VERSION = "governed-policy-corpus-v1"
GOVERNED_CHUNKING_VERSION = "markdown-clause-v1"
GOVERNED_INDEX_VERSION = "governed-policy-index-v1"


def parse_policy_source(
    source_text: str,
    applicability: PolicyApplicability,
) -> list[ParsedPolicyClause]:
    normalized = source_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(normalized) < 20:
        raise PolicySourceParseError("Policy source text is too short to parse safely.")

    clauses: list[ParsedPolicyClause] = []
    heading = "Policy clause"
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        text = "\n".join(body).strip()
        body = []
        if not text:
            return
        if len(text) < 20:
            raise PolicySourceParseError(f"Clause '{heading}' is too short to use as evidence.")
        clauses.append(
            ParsedPolicyClause(
                heading=heading,
                text=text,
                applies_when=_applicability_label(applicability),
            )
        )

    for line in normalized.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            flush()
            parsed_heading = stripped.lstrip("#").strip()
            if not parsed_heading:
                raise PolicySourceParseError("Policy heading cannot be blank.")
            heading = parsed_heading[:300]
            continue
        if not stripped and body and body[-1] != "":
            body.append("")
        elif stripped:
            body.append(stripped)
    flush()

    if not clauses:
        raise PolicySourceParseError("Policy source contains no usable clauses.")
    if len(clauses) > 100:
        raise PolicySourceParseError("Policy source contains more than 100 clauses.")
    return clauses


def _applicability_label(applicability: PolicyApplicability) -> str:
    categories = ", ".join(str(value) for value in applicability.case_categories)
    return (
        f"Scope {applicability.decision_scope}; categories {categories}; "
        f"products {', '.join(applicability.products)}; "
        f"regions {', '.join(applicability.regions)}; "
        f"channels {', '.join(applicability.channels)}; "
        f"customer tiers {', '.join(applicability.customer_tiers)}."
    )
