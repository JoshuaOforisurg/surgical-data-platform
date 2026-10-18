# Platform and Surgeon Preference Review

Status: working review note, not a production-readiness approval.
Scope: current repository state reviewed 2026-10-18. No changes from this review
have been committed.

Follow-up: the first local hardening slice now rejects identity-provider role
claims as app permissions and disables protected actions when the Postgres
registry is unavailable. This does not yet provide membership-scoped roles or
gate tenant data reads; the findings below remain open until those controls and
two-tenant tests are complete.

## Candid platform assessment

This is a thoughtful, differentiated data-engineering prototype with a real
operating-theatre problem behind it. Surgeon Preference is the strongest
vertical slice. The Preference -> Stock -> Loan Kit direction is coherent.
However, the platform is not ready for live clinical operations or a public,
multi-organisation launch. The main gap is not feature count; it is reliable,
demonstrable behavior under failure and trustworthy authorization boundaries.

Current subjective assessment:

- Domain and product thinking: strong, approximately 8/10.
- Prototype engineering maturity: meaningful, approximately 6/10.
- Production and multi-tenant readiness: low, approximately 2-3/10.

These are review judgments, not measured quality scores.

## Platform findings

1. **Keep the product boundary narrow.** Surgeon Preference is the best-developed
   product path. Stock is promising but still needs enforced quality gates and
   proven recovery behavior. Loan Kit describes itself as an early technical
   skeleton, not a validated or deployed workflow. Do not connect all three into
   a readiness decision until their contracts and failure semantics are proven.

2. **Stock publishing does not enforce its quality gate.** The Stock runner
   proceeds through Gold, while quality evaluation is separate. The artifact
   publisher uploads from the run manifest without requiring a passing quality
   result. Publishing must fail closed unless required gates passed for that
   exact run.

3. **End-to-end retry/recovery is not yet proven.** Unit tests are useful, but a
   live multi-service integration run did not complete. The malformed-file
   quarantine path should not be described as end-to-end proven until a
   repeatable integration test demonstrates valid sibling processing,
   quarantine registration, rerun behavior, and no duplicate/corrupt Gold.

4. **Local service ports should be loopback-only.** The Compose configuration
   publishes Streamlit, MinIO, and Postgres ports without restricting the host
   binding. Bind local development ports to `127.0.0.1` and keep production
   exposure behind the intended ingress.

5. **Claims and evidence need to stay synchronized.** Deployment evidence and
   roadmap material are stale or broader than the demonstrated system. Clearly
   label implemented, tested locally, deployed, and future capabilities
   separately. Friday's realistic target is a dependable demo slice, not a
   worldwide clinical product.

## Surgeon Preference multi-tenant assessment

The app has useful foundations: authenticated identity extraction, role checks,
access requests, draft/review/publish workflow, version history, and organisation
IDs on important records. These are good foundations, but the current model is
single-workspace-oriented with organisation labels, not yet a defensible
multi-tenant security boundary.

### Highest-priority findings

1. **Tenant membership is configuration-driven, not established by membership.**
   `APP_ORGANISATION_ID` is assigned to the identity, and the app then treats it
   as the active organisation. There is no user-visible, database-validated
   membership selection for a user belonging to multiple organisations.

2. **User identity is globally keyed by email.** `app_users` uses a global
   user identity/default organisation model. The upsert replaces
   `default_organisation_id` on every sign-in. That cannot correctly represent
   one person who belongs to multiple hospitals, with different roles in each.
   Authoritative permissions should live on `(organisation_id, user_id)`
   memberships; user profile and tenant membership are separate concepts.

3. **Database unavailability falls back to identity/allowlist roles.** When the
   registry cannot be reached, `sync_user_with_registry` returns the identity
   user with a warning. This may be acceptable for a local demo, but for a
   multi-tenant product authorization should fail closed: no tenant-bound read
   or write unless the user's active membership and permissions were resolved.

4. **Identity and registry roles are unioned.** The merged user combines role
   claims from the identity provider with database roles. This makes it unclear
   which system is authoritative and can preserve a privileged identity claim
   after an administrator removes that role in the app registry. Pick one
   authority for app roles; use identity claims for verified identity and
   coarse app assignment only if explicitly designed that way.

5. **Organisation scoping is partly a storage-prefix convention.** Drafts are
   listed from a shared prefix and filtered after reading their payloads;
   review and publish event counts also list shared prefixes. This is not
   necessarily a direct data leak by itself, but it is a fragile boundary,
   exposes cross-tenant metadata/counts, and makes every call site responsible
   for correct filtering. Prefer tenant-scoped storage paths and repository
   methods that require tenant context, with database row-level safeguards for
   operational records.

6. **Access request semantics do not yet establish a new tenant.** A request
   includes a requested organisation name, but the signed-in user's existing
   organisation ID is used for persistence. Joining an existing organisation,
   creating a new organisation, and approving its first administrator are
   distinct workflows and need explicit, authorized transitions.

7. **The current UI is an operational demo, not a complete tenant onboarding
   product.** Users cannot yet reliably create an organisation, invite colleagues,
   manage multiple memberships, select an active workspace, or understand their
   access state without admin intervention. This is a product gap as well as a
   schema gap.

8. **Data isolation has not been demonstrated with adversarial tests.** Add
   tests with two organisations and users, including cross-tenant read, search,
   draft review, publish, rollback, access-request, and storage-key attempts.
   Assert that no rows, object contents, counts, or action outcomes cross the
   tenant boundary.

## Recommended build order

1. **Define the tenant and membership contract.** Separate global user identity,
   organisation, membership, and role. Specify how a user joins or creates an
   organisation and how the first admin is trusted.
2. **Make tenant context mandatory.** Resolve the active organisation from a
   verified membership; reject missing, suspended, or unauthorized membership.
   Do not accept a client-supplied organisation ID as authorization.
3. **Fail closed for protected operations.** If the authorization registry is
   unavailable, disable tenant data reads and every mutation. Keep any public
   synthetic demo path explicitly separate.
4. **Enforce tenant isolation in persistence.** Scope every SQL query and object
   key. Consider PostgreSQL row-level security as defense in depth, not a
   replacement for application authorization.
5. **Add two-tenant isolation tests before onboarding UI.** Prove reads and all
   mutations are isolated, including counts and error paths.
6. **Build onboarding and membership management.** Organization creation,
   invitations/access requests, membership approval, role assignment, and
   workspace switching should follow the verified data model.
7. **Then deploy a controlled pilot.** Add audit review, backup/restore,
   monitoring, incident response, retention policy, and appropriate clinical
   safety/privacy governance before real preference data is accepted.

## Immediate product boundary

Continue with synthetic data and a controlled demo. Do not accept real hospital
preference cards or describe the service as globally available until tenant
isolation is demonstrated and the required privacy, security, operational, and
clinical governance work is complete.
