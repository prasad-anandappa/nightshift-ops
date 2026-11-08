# Chaos panel — reproducible faults, on demand (DESIGN §3, Nov 4)

Four faults, each reversible by an allowlisted tool:
1. Kill process        -> fixed by restart_service
2. Fill disk           -> fixed by clear_temp_files
3. Ship bad deploy     -> fixed by rollback_deploy
4. Spike error rate    -> diagnosed via read_logs, fixed per plan

TODO (Nov 4): one script/endpoint per fault + a small operator UI.
TODO (Nov 7): the demo uses "Ship bad deploy" as the on-camera break (DESIGN §4).
