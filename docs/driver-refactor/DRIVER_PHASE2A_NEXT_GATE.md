# Driver Phase 2A Next Gate

## Phase 2A status

The local isolated actual-node data chain is ready for Phase 2B integration. This statement does not authorize or claim Trial deployment.

## Gate before Phase 2B

1. Review and accept the GET/POST contract and the one-odometer-per-node boundary.
2. Independently review the additive migration and the audit retention policy.
3. Keep the Phase 1 home, old task page and five-tab navigation unchanged.
4. Phase 2B may bind its six visible fields only to these two routes; it must not create another order/report/notification store.
5. Generate a unique `client_request_id` per logical save and retain it for network retry.
6. Send the displayed `document_version_id`, `source_sha256`, node `revision`, assignment and order binding.
7. On HTTP 409, display/reload the server current state; do not silently overwrite.
8. Preserve full ISO dates for cross-midnight timestamps.

## Still outside this gate

- Six-field two-column/three-row phone editor, keyboard behavior and real-device interaction.
- Formal daily-report PDF and signature/approval flow.
- Trial migration/deployment or service restart.
- Production access, WeChat upload, document publication and real notifications.

## Phase 2B minimum files expected

Only the existing driver task/home UI and API wrapper necessary to consume Phase 2A should change. No bottom navigation, parallel API client, database schema, PDF renderer, expense module or report state-machine redesign is justified by this gate.
