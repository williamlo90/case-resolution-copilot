# Frontend Engineering Conventions

## Folder rules

- `app/`: routes, layouts, boundaries, and composition only.
- `features/`: behavior and UI owned by one product capability.
- `domain/`: framework-independent contracts and schemas.
- `data/`: repository interfaces, adapters, and query definitions.
- `components/ui/`: low-level accessible primitives.
- Other `components/` folders: cross-route layout, navigation, access, provider, and accessibility
  boundaries.
- `mocks/`: deterministic fixtures, scenarios, and mock adapters.
- `lib/`: narrow infrastructure integrations with explicit names.

Forbidden dumping grounds: `utils/`, `helpers/`, `shared/`, `common/`, or `misc/` without a precise documented responsibility.

## Naming

- Components and types: PascalCase (`PolicyEvidencePanel`, `TaskSummary`).
- Hooks: `use` + capability (`useTaskFilters`).
- Schemas: domain name + `Schema` (`TaskSummarySchema`).
- Repository interfaces: capability + `Repository` (`TaskRepository`).
- Mock scenarios: behavior-based (`refundNeedsApprovalScenario`).
- Boolean names describe truth (`isStale`, `requiresApproval`).
- Event handlers describe intent (`handleApproveRefund`).

Avoid generic names such as `Card2`, `PanelA`, `DataItem`, `Manager`, `Helper`, or `handleClick` when domain intent is known.

## Import direction

```text
app → features → components/domain/data → lib
```

Domain contracts do not import React, Next.js, or feature components. Mock data never becomes the canonical domain model.

## Component rule

Keep a component local to its feature until a second real consumer or normative cross-screen contract exists. Extract behavior, not visual coincidence.
