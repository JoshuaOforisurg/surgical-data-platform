# Preference Card Rollback And Revert Design

## Goal

Allow an authorised admin to revert a current surgeon preference card to a
previously published version without deleting or rewriting history.

Rollback must be safe, auditable, and easy to explain:

```text
Current version v5 is wrong.
Admin chooses previous version v3.
The system creates v6 as a copy of v3.
v6 becomes current.
v1-v5 remain in the history forever.
```

This design avoids time-travel confusion. The latest current version is always
the highest version number, even when its content came from an older version.

## Why Not Just Mark The Old Version Current?

Do not simply flip `is_current=true` on an old row.

That would make the card history harder to reason about:

```text
v5 was current
then v3 became current again
```

A user could ask: what happened after v5? The answer would be hidden in a flag
change rather than visible as a new operational event.

Preferred model:

```text
v5 current and incorrect
v6 created from v3 as a rollback
v6 current
```

That gives a clear chain of operational decisions.

## User Workflow

In Streamlit, an admin opens a current preference card and sees version
history:

```text
v5 current
v4 previous
v3 previous
v2 previous
v1 imported
```

For a selected historical version, the admin can choose:

```text
Review this version
Revert to this version
```

Before reverting, the app should show:

- current version
- selected historical version
- fields that will change
- revert reason text box
- confirmation checkbox

The admin must explicitly confirm:

```text
I understand this will create a new current version copied from the selected
historical version.
```

## Roles

Only admins should be able to perform rollback/revert.

Reviewers may inspect history, but should not revert cards unless they also
have the admin role.

## Data Model

Existing tables:

```text
app_workflow.preference_cards
app_workflow.preference_card_versions
app_workflow.audit_events
```

Implemented additional columns on `preference_card_versions`:

```text
change_type TEXT
source_version_id UUID
change_reason TEXT
```

Implemented values for `change_type`:

```text
pipeline_import
draft_publish
rollback
manual_admin_repair
```

For rollback:

```text
new version row:
  version_number = current_version_number + 1
  card_payload = selected historical version payload
  is_current = true
  change_type = 'rollback'
  source_version_id = selected historical version_id
  change_reason = admin-entered reason
  published_by = admin email/name
  published_at = now
```

The previous current version should be updated:

```text
is_current = false
```

The parent card should be updated:

```text
current_version_id = new rollback version_id
current_version_number = new version number
updated_at = now
```

## Audit Event

Rollback should create an audit event:

```text
event_type = preference_card_rollback_published
entity_type = preference_card
entity_id = card_id
actor_email = admin email
event_payload = {
  card_id,
  rollback_version_id,
  source_version_id,
  from_version_number,
  to_version_number,
  rollback_reason,
  surgeon_name,
  procedure_name,
  organisation_id
}
```

## Gold Export Behaviour

Postgres remains the operational source of truth.

After rollback succeeds:

1. Load all current cards from Postgres.
2. Export a new Gold operational CSV/JSON snapshot.
3. Save a publish/revert event object in object storage.
4. Clear Streamlit caches.

Gold should not drive the rollback decision. Gold is the snapshot produced
after the operational database update succeeds.

## Failure Behaviour

Rollback must be transactional in Postgres.

If the new version cannot be created:

- do not change `current_version_id`
- do not change `is_current`
- do not export Gold
- show the admin an error

If Postgres rollback succeeds but Gold export fails:

- keep the Postgres rollback because it is the operational source of truth
- record warning/audit that Gold export failed
- product readiness should report Gold snapshot as stale or out of sync

## Frontend Placement

Recommended first implementation:

- Add rollback controls inside the existing "Preference cards" tab below
  version history.
- Only show the controls when:
  - data source is Postgres
  - a specific procedure is selected
  - the user can publish/administer preference cards
  - there is more than one historical version

Later implementation:

- Move rollback into a dedicated admin "Version history" or "Card governance"
  screen when the product frontend grows beyond Streamlit.

## Tests To Keep Expanding

Repository tests should cover:

- cannot rollback when Postgres settings are missing
- cannot rollback to current version
- cannot rollback to a version from another organisation
- rollback creates a new highest version
- rollback copies the selected historical payload
- rollback marks exactly one version current
- rollback records source version and reason

App/service tests:

- non-admin cannot see/perform rollback
- rollback clears current-card and history caches
- Gold export runs after rollback
- Gold export failure does not corrupt Postgres state

## Acceptance Criteria

The rollback feature is complete when:

- an admin can revert a selected current card to a previous version
- the revert creates a new version, not a destructive overwrite
- version history clearly shows the rollback version
- audit history records who reverted, when, from which version, and why
- Streamlit shows the reverted card as current
- Gold latest is refreshed after rollback
- tests prove cross-organisation isolation
