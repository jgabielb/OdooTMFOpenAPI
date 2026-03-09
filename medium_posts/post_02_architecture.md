# Building TM Forum Open APIs on Odoo: Project Architecture

In the first post, I explained why combining Odoo and TM Forum Open APIs makes sense.

This second post is about **how** I structured the project so it can scale across many TMF domains while staying maintainable.

## Architecture Goals

The architecture was designed around four practical goals:

1. Keep business data anchored in Odoo models
2. Expose TMF-compliant REST endpoints per domain
3. Reuse shared logic instead of duplicating code in every API
4. Validate continuously with smoke tests and CTK runs

## High-Level Structure

The project follows a modular Odoo addon layout:

- One addon per TMF domain (for example: customer, catalog, order, incident, etc.)
- A shared base addon (`tmf_base`) for common behavior
- Tooling scripts for smoke tests and CTK batch execution

This gives a clear separation:

- **Domain addons** implement domain-specific resources and routes
- **Base addon** handles common patterns (IDs, payload normalization, webhook/event helpers, shared UI conventions)
- **Tools** provide repeatable verification

## Request Flow

A typical API request follows this path:

1. HTTP request hits a TMF route in a domain controller
2. Controller validates/parses payload and query parameters
3. Controller calls Odoo model methods (create/search/write/unlink)
4. Model maps data to TMF JSON response format
5. Response is returned with expected status code and headers

This keeps controllers thin and pushes mapping/business consistency into models.

## Shared Cross-Cutting Pieces

Across all APIs, some concerns repeat. These are centralized:

- TMF ID and href generation
- Field mapping between TMF payloads and Odoo fields
- Consistent error response shapes
- Event/webhook dispatch support
- UI normalization for menu/action consistency

Without this shared layer, each module would drift and CTK remediation would become expensive.

## Why This Scales

The project supports many TMF APIs, and that only works if adding a new domain is predictable.

The current pattern makes expansion straightforward:

1. Create addon scaffold
2. Add models and controller routes
3. Reuse shared helpers
4. Add smoke scenario
5. Run CTK and close gaps

This is faster than custom one-off implementations because every new API starts from proven conventions.

## Testing and Conformance Layer

Two test layers are used:

- **Smoke test**: quick CRUD and endpoint behavior checks across many APIs
- **CTK batch**: conformance validation per TMF API and version

This combination helps catch both:

- runtime regressions during development
- standard-compliance regressions over time

## Practical Tradeoffs

A few intentional tradeoffs were made:

- Prefer clear, explicit module boundaries over over-abstracting everything
- Keep TMF payload mapping close to the domain model for readability
- Use shared utilities only for truly repeated behavior

This keeps the codebase understandable for both Odoo developers and API/integration engineers.

## What’s Next

In Post 3, I’ll go deeper into implementation details: recurring failure patterns, CTK-driven fixes, and how specific issues were resolved during development.
