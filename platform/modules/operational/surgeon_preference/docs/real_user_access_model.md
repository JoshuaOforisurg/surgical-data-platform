# Real User Access Model

This app should not manage passwords itself. For the first usable product
version, Azure should authenticate people and the app should authorise what
they can do.

## Target Flow

1. A visitor opens `https://www.surgeonpreference.com`.
2. Public visitors can view demo/synthetic preference-card data.
3. A visitor clicks sign in.
4. Azure Container Apps Authentication validates the person through the
   configured identity provider.
5. Azure forwards identity headers to Streamlit.
6. Streamlit records or updates the user in `app_workflow.app_users`.
7. A non-approved user submits an access request from the Access tab.
8. An administrator reviews the request in the Access tab.
9. Approved users receive only the minimum role they need:
   - `authenticated`: signed-in user with no edit privileges
   - `editor`: can submit draft preference-card changes
   - `reviewer`: can review submitted draft changes
   - `admin`: can manage users and access requests
10. All approvals, role changes, draft reviews, and publishes are written to
    Postgres audit tables.

## Azure Responsibilities

Azure Container Apps Authentication should handle:

- sign-in
- sign-out
- identity-provider integration
- forwarding user identity headers to the app

Recommended first provider:

- Microsoft Entra ID for a private or NHS-style pilot

Possible later providers:

- Google for external public users
- GitHub for technical collaborators

## App Responsibilities

The Streamlit app handles product permissions after Azure has identified the
user:

- create a pending user record
- allow access requests
- allow admins to approve or reject access requests
- allow draft creation only for approved editors/admins
- allow review only for approved reviewers/admins
- allow publishing only for approved admins

The app should not:

- store user passwords
- send password-reset emails
- accept patient-identifiable data
- allow public users to edit published cards
- expose admin actions without an authenticated approved admin

## Environment Flags

For a production-like deployment, configure these on the Container App:

```bash
APP_AUTH_PROVIDERS=aad
APP_SHOW_AUTH_LINKS=true
APP_ADMIN_ALLOWLIST=your-admin-email@example.com
ENABLE_DRAFT_SUBMISSIONS=true
ENABLE_DRAFT_REVIEWS=true
ENABLE_DRAFT_PUBLISHING=true
```

The first admin should be pre-registered through the Access tab or by running
the Postgres bootstrap/user setup script. After that, normal users should use
the request-and-approval flow.

## Database Objects

The access model depends on the `app_workflow` schema:

- `app_workflow.organisations`
- `app_workflow.app_users`
- `app_workflow.organisation_memberships`
- `app_workflow.access_requests`
- `app_workflow.draft_reviews`
- `app_workflow.audit_events`

Run `sql/azure_postgres_bootstrap.sql` against Azure Postgres before enabling
real users.

## Current Product Boundary

This remains a synthetic-data product. Do not collect real patient data,
patient identifiers, theatre lists, or confidential hospital preference cards
until the platform has:

- tenant isolation
- data processing agreements
- clinical safety review
- backup and restore checks
- monitoring and incident response
- role-based access tested in Azure
- a clear data retention policy

## Next Build Steps

1. Enable Azure Container Apps Authentication on the web Container App.
2. Configure Microsoft Entra ID as the first identity provider.
3. Keep unauthenticated access allowed only if public demo viewing remains
   intentional.
4. Deploy the latest image with auth links enabled.
5. Sign in as the first admin account.
6. Submit a test access request from a second account.
7. Approve/reject the request and confirm the audit trail in Postgres.
