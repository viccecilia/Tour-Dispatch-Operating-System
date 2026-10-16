# Driver continuous rollback plan

## General rules

- Do not reset or clean the dirty worktree.
- Revert only reviewed M1 code paths, preferably behind existing/new narrow UI entry points.
- Additive database changes must not be undone by restoring an old database over newer writes. If writes exist, disable entry points and use a forward compatibility repair.
- Preserve provisional originals/events, Phase 2A actual-node rows and all existing published document/history rows.

## M0

Only evidence Markdown files were added. They can be removed from a review bundle without touching runtime code or data.

## M1

1. Disable the `provisional-orders` Web navigation permission and the miniapp provisional entry points. This leaves all B0-A records queryable and does not delete history.
2. Disable the pricing/summary route dispatches while retaining the linked formal orders and append-only events. Never delete a formal order created from an approved temporary task.
3. Revert only the M1 page/API bindings after reviewing the pre-existing dirty changes in shared home/task files; do not reset the worktree.
4. The two odometer columns are additive and nullable. Safe rollback is to stop writing them and retain them. Do not drop them after any M1 write; older code ignores them.
5. If the migration has not been used outside an isolated copy, restore only that isolated database from its rehearsal backup. Never copy the local acceptance DB over Trial/Production.
6. Retain `client_request_id`, task revisions, event rows, `origin_kind` and `origin_provisional_task_id`; these are the anti-duplicate and audit chain.
7. Re-run the 25-test targeted suite, the miniapp checker and Web build after any rollback patch.

No live rollback is currently required: M1 was not deployed, committed, pushed or uploaded.
