# Complex Case Decision Workflow Usability Study Protocol

Status: `PLANNED_NOT_RUN`

This protocol prevents an internal walkthrough or automated test from being reported as user
research. Do not add results until sessions have been observed and private raw notes are retained.

## Research Question

Can a support specialist or supervisor understand a complex case that needs review, distinguish
verified facts from missing information, identify the approval boundary, and choose a safe next
step without product explanation?

## Participants

- Three to five people familiar with customer support, operations, complaints, refunds, or
  supervisory approval.
- Include at least one participant who regularly handles complex or exception cases and one who
  approves exceptions.
- Do not use the builder as a participant.
- Record role and experience band only. Do not record employer, customer, or unnecessary personal
  information.
- Use synthetic cases and a reversible action simulator only.

## Tasks

1. Find a high-risk case that needs attention.
2. Explain the issue using the verified facts and identify what information is still missing.
3. Identify which policy guidance applies and whether it is current or conflicting.
4. Review the recommended resolution and explain what remains uncertain.
5. Prepare a customer reply and submit the resolution for review.
6. As a supervisor, identify what the approval would authorize and decide whether to approve,
   request changes, reject, or escalate.
7. Given an action with an unknown outcome, choose the safe recovery step without retrying it.

The facilitator must not explain navigation or terminology during the first attempt. Assistance may
be given after the participant is visibly blocked, but the exact hint and timing must be recorded.

## Measures

| Measure | Recording rule |
| --- | --- |
| Task completion | Complete, complete with help, or incomplete |
| Unsafe action attempt | Count every attempt to approve or retry while a blocker remains |
| Time on task | Start at the task prompt and stop at the visible authoritative outcome |
| Assistance | Record the exact hint and when it was needed |
| Evidence comprehension | Participant explains what is verified and what is missing |
| Approval comprehension | Participant explains what their decision would authorize |
| Recovery comprehension | Participant explains why an unknown outcome cannot be retried blindly |
| Navigation error | Participant opens an unrelated primary page before finding the task |
| Terminology issue | Participant misinterprets an on-screen term |
| Confidence | One 1-5 rating after the full journey, reported per participant |

## Session Record

Keep raw notes outside Git. The public report may contain only an anonymous aggregate:

| Participant | Experience | Completed without help | Unsafe attempts | Median task time | Main confusion |
| --- | --- | ---: | ---: | ---: | --- |
| P1 | Pending | Pending | Pending | Pending | Pending |

## Decision Rules

- Any unsafe action that the backend permits is a release-blocking defect.
- Two participants failing the same task without help creates a usability issue.
- A term misunderstood by two participants must be rewritten before adding more UI.
- A repeated navigation error requires an information-architecture or label change.
- Do not claim percentage improvement without a measured manual baseline and a meaningful
  comparative sample.
- Do not convert task time into labor or cost savings without measured business data.

## Reporting Boundary

Publish participant experience bands, task outcomes, assistance, observed errors, changes made, and
unresolved findings. Do not publish names, employers, customer records, recordings, or raw notes.
Do not turn this small study into a production-readiness or business-impact claim.
