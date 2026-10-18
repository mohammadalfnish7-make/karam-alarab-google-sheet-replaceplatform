# Feature: Intake weight policy (implementation)

Status: **documented, not fully implemented** — policy locked in [docs/intake-weight-policy.md](../docs/intake-weight-policy.md).

Build when ready (after demos / before operator tutorials):

1. Tolerance X (default 1 kg): Match / OK ≤ X (confirm) / Conflict (block save).
2. Editable extract fields; Use scale / Use hand / Re-check / Remove.
3. Persist extract + overrides; audit original/override/who/why; agent override events.
4. `needs_review` when scale field overridden.
5. Multi-pallet totals from preferred per photo; net = TW − PW.
