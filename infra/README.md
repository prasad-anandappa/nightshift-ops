# Infrastructure — Vultr provisioning notes

Provisioned at kickoff (Nov 3, after the user's account step — DESIGN §7):
- Control-plane Cloud Compute instance (agent + dashboard, always on, public demo URL)
- Sandbox Cloud Compute instance (disposable; snapshot golden image once the fleet runs)
- Cloud Firewall group: sandbox inbound = control plane + operator IP only; restricted egress
- Managed PostgreSQL (agent memory + audit store)
- Object Storage bucket: nightshift-ops
- Serverless Inference: confirm access, pick model from catalog, one smoke call

TODO (Nov 3): record instance sizes/regions actually provisioned + monthly burn.
TODO: lifecycle discipline — reset/rebuild sandbox from snapshot after drills
(live brief). Stop the sandbox outside build hours if credits run tight.
