## Context

See `proposal.md` for motivation. The version-three callback selection has no input field, reconciliation invokes selected operations with `None`, and after-cohort dispatch binds the first completed repository once. The extension runtime already has managed-value validation/freezing utilities, per-repository binding, immutable events, structured callback outcomes, and structural callback evidence that this change can extend without a new dependency.

## Goals / Non-Goals

**Goals:**

- Make a callback selection a stable value containing validated immutable input.
- Preserve the exact input through planning, drift validation, and operation invocation.
- Fan one after-cohort selection out into deterministic repository-isolated invocations after integration is complete.
- Retain the existing core-owned reconciliation and observational outcome semantics.

**Non-Goals:**

- Inferring ZPP commands or interpreting extension payload schemas.
- Adding aggregate cross-repository configuration, retry state, post-mutation gates, or compatibility adapters for version three.
- Changing ordinary operation input, Git integration order, or reconciliation member statuses.

## Decisions

### Freeze callback input at public construction

`CallbackSelection` will validate and recursively freeze its non-`None` `input` in `__post_init__`, using the same managed-value boundary used by configuration. `None` remains the explicit no-input sentinel, so callers selecting callbacks without a payload retain concise construction while v3 registrations are rejected by the version bump. Freezing at construction prevents caller mutation between plan and apply and gives structural evidence a deterministic value.

Alternative: accept arbitrary opaque Python objects like manual operation input. Rejected because mutable or non-structural objects cannot provide trustworthy plan evidence or drift behavior.

### Include input in the callback plan record

The plan's callback entry will include the frozen input directly; the existing structural evidence will therefore cover it automatically. Dispatch will pass `selection.input` to the runtime invocation without transformation or configuration lookup.

Alternative: store only an input digest. Rejected because the owner must be able to inspect the exact planned callback request and the runtime already treats managed values as bounded serializable data.

### Fan out after-cohort selections at dispatch time

After every selected integration succeeds, reconciliation will iterate completed repository ids in their existing deterministic order and invoke each selected after-cohort callback for each repository. `_dispatch_reconcile_callback` will bind that repository and construct an event containing both `cohort_id=space_id` and `repository_id` for all reconciliation events.

Alternative: create one synthetic aggregate context. Rejected because extension configuration and behavior scopes are repository-specific, and combining them would require precedence and write-authority policy outside this change.

### Preserve selection order within each repository

For each completed repository, after-cohort callbacks run in caller selection order. An observational failure is appended as its own outcome and dispatch continues to later callbacks and repositories. This matches existing observational callback behavior and makes the outcome sequence correspond to repository order, then callback order.

Alternative: run all repositories for the first callback before moving to the next callback. Rejected because repository-major ordering aligns outcomes with reconciliation order and keeps each isolated repository behavior phase contiguous.

## Risks / Trade-offs

- [The v4 bump requires dependent registrations to update even if they do not use callbacks] → Reject v3 clearly and document that no compatibility path exists.
- [A callback input may contain sensitive values visible in a plan] → Keep the managed-value boundary and document that callback input is explicit plan data; callers should pass references rather than secrets requiring redaction.
- [One selection now yields multiple outcomes] → Preserve a flat deterministic outcome tuple/list and test cardinality and ordering explicitly.
- [A late observational failure cannot undo completed Git work] → Keep the existing truthful post-mutation semantics and continue remaining invocations.

## Migration Plan

1. Advance the public extension contract constant and registrations to version four.
2. Add and freeze callback selection input, include it in planning, and pass it to dispatch.
3. Replace the single first-repository after-cohort dispatch with repository-major fan-out.
4. Update dependent tests, BDD coverage, and documentation; no persisted-state migration is required because callback selections and plans are not durable lifecycle state.
5. A dependent ZPP integration can then select its command explicitly and consume repository-isolated callback contexts.
