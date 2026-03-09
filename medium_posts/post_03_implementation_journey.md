# Building TM Forum Open APIs on Odoo: Implementation Journey

In this post, I’ll share the implementation side: what worked, what failed, and what patterns made the project stable at scale.

## Starting Point

The target was ambitious: implement many TMF APIs on top of Odoo and keep them operationally useful, not just technically exposed.

From day one, the project had two constraints:

1. APIs had to be wired to real Odoo data and workflows
2. APIs had to pass CTK conformance checks

That dual constraint shaped every technical decision.

## Early Pattern: Domain Module + Shared Base

The first useful pattern was to treat each TMF domain as its own addon, while keeping shared behavior in `tmf_base`.

This prevented copy/paste growth and helped standardize:

- endpoint conventions
- response envelope patterns
- id/href mapping
- event subscription handling

## CTK as the Real Feedback Loop

Implementation alone was not enough. The real quality gate was CTK.

The process became iterative:

1. Implement endpoint and model mapping
2. Run CTK
3. Inspect assertion-level failures
4. Patch controller/model behavior
5. Re-run until green

This revealed issues that are easy to miss in manual testing.

## Common Failure Patterns We Hit

Several failure families repeated across APIs:

- Wrong base URL/host behavior between Docker and non-Docker CTKs
- Status code mismatches (for example expected 204 vs returned 404/405)
- Missing mandatory attributes in responses
- Filtering behavior mismatches (`id`, `name`, `fields` handling)
- Patch/delete semantics not aligned with specific CTK expectations
- Recursive model write loops causing `maximum recursion depth exceeded`

Fixing these systematically improved both conformance and runtime stability.

## Automation Improvements

To reduce manual effort, I improved tooling in parallel with API code:

- Batch CTK runner across many APIs
- Better config overrides for base URL handling
- Parallel execution with configurable workers
- Smoke test expansion to cover more scenarios/resources

This shifted validation from ad hoc runs to repeatable workflows.

## One Important Lesson

A major lesson was this: conformance issues are often not “big bugs,” but small contract deviations repeated many times.

Examples:

- A missing field in one response path
- A route alias missing uppercase/lowercase variant
- A create flow that works functionally but returns wrong shape

At TMF scale, consistency is everything.

## Engineering Discipline That Helped

Three practices made progress consistent:

1. Keep controller logic explicit and readable
2. Keep model JSON mapping deterministic
3. Validate after every meaningful change

When these were followed, fixes stayed local and regressions dropped.

## Current State

At this stage, a broad set of APIs are implemented and validated through smoke + CTK workflows, with continuous cleanup of edge cases discovered during reruns.

The codebase is now much closer to a reusable telecom integration foundation on Odoo, not just a prototype.

## What’s Next

In Post 4, I’ll move from engineering internals to business flows: subscriber onboarding, one-time sales, recurring products, device changes, and cancellation — all mapped to Odoo CRM/Sales/Inventory operations with TMF APIs on top.
