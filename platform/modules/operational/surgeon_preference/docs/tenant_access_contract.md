# Surgeon Preference Tenant Access Contract

Status: implementation in progress. Membership-scoped reads and protected
transactional writes are implemented and locally tested. Keep real
organisation data disabled until all acceptance checks below pass and Azure
deployment validation is complete.

Implementation progress: app roles and status are now resolved from the
organisation membership row for the configured workspace. Routine sign-in only
updates the global user profile; it no longer creates or rewrites a membership.
Admin membership updates, access-request decisions, and workflow metadata are
organisation-scoped. Users with multiple active memberships can now select
among them, and users without an active membership are kept out of the tenant
workflow UI. Public browsing is limited to the explicitly enabled synthetic
demo. Tenant fallback refuses the global Gold snapshot unless it carries a
matching organisation ID. Azure/OIDC provider-qualified subject IDs are now
captured and persisted on the global user profile, with conflicting identity
bindings rejected. Memberships still use email as their foreign key, so
verified account linking and email-change migration remain outstanding.
Protected app writes re-resolve active membership and roles before draft,
review, publish, rollback, and organisation-admin actions. Core repository
mutations also lock and validate the actor's active membership and required
role in the write transaction. A disposable two-tenant Postgres test now covers
card read/history isolation, tenant-scoped drafts, publish/rollback roles, and
membership administration. PostgreSQL row-level security and a comprehensive
cross-workflow adversarial matrix remain outstanding. Email changes still need
an audited identity migration.

## Domain Model

- **Identity**: the authenticated person, keyed by the identity provider's
  stable subject identifier and provider. Email and display name are mutable
  profile attributes, not authorization keys.
- **Organisation**: one hospital, trust, provider group, or other customer
  boundary.
- **Membership**: the relationship between one identity and one organisation.
  Membership owns the organisation-specific status and roles.
- **Active organisation**: a server-resolved organisation for the current
  request/session, selected only from that identity's active memberships.

One identity may have memberships in many organisations and may have different
roles in each. A user's global profile must not contain the authoritative
organisation role. `APP_ORGANISATION_ID` may identify a local demo tenant, but
must never authorize production tenant access.

## Authorization Rules

1. Authentication establishes identity only; it does not grant tenant access.
2. Tenant access requires an active database membership for the authenticated
   identity and selected organisation.
3. The selected organisation is validated server-side on every protected
   operation. A browser/session value is a request, not proof of membership.
4. Application roles come from the active organisation membership. Identity
   provider claims do not override or union with database app roles.
5. If the membership store is unavailable, tenant-scoped reads and all
   mutations fail closed. A separately configured synthetic demo may remain
   publicly readable, but it must not share a path to customer data.
6. Every operational SQL query, object key, audit event, draft, review,
   publish, rollback, access request, and displayed count is scoped to the
   validated organisation.
7. Cross-organisation actions require an explicit, separately authorized
   platform-support capability and must be audited.

## Onboarding Boundaries

- Joining an existing organisation requires an invitation or approval by an
  administrator of that organisation.
- Creating an organisation creates a pending organisation and a pending
  membership request; it does not grant administrator privileges immediately.
- A trusted bootstrap process grants the first organisation administrator.
- Access requests cannot create an active organisation or self-assign roles.
- Suspending a membership removes access to that organisation without
  suspending the person's memberships elsewhere.

## Data and Storage Rules

- Tenant-owned database tables carry a non-null `organisation_id` and use it in
  unique keys and foreign-key relationships where appropriate.
- Repository methods for tenant-owned data require an explicit validated
  tenant context; no implicit `default` tenant is allowed on production paths.
- Object keys use a canonical tenant prefix, for example
  `organisations/{organisation_id}/...`.
- PostgreSQL row-level security may be added as defense in depth, but application
  authorization remains required. RLS context must be transaction-scoped and
  reliably cleared when pooled connections are reused.
- Logs and metrics must not reveal another tenant's names, counts, object keys,
  or clinical preference content.

## Acceptance Checks Before Real Tenant Data

- A user can belong to two organisations with distinct roles and switch only
  between memberships that are active.
- Tenant A cannot read, search, count, edit, review, publish, roll back, or infer
  Tenant B data by changing IDs, URLs, form values, object keys, or session state.
  Current local integration coverage is partial; extend it to access requests,
  counts, and all failure paths before claiming this acceptance check is met.
- A suspended user loses access to the affected tenant immediately without
  changing other tenant memberships.
- Database or membership-resolution failure blocks protected tenant operations.
- Access requests cannot grant access or privilege before an authorized
  approval.
- Tests cover SQL repositories, object storage, Streamlit workflows, and
  failure paths with at least two tenants.
- A migration and rollback path preserves the existing synthetic `default`
  workspace without silently assigning real customers to it.
