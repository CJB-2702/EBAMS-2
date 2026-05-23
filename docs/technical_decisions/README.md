# `technical_decisions/` — folder structure

Per-event detail for the locked decisions, tech debt, and incident takeaways summarised in [../technical_decisions.md](../technical_decisions.md). Format specification: [../Context_Scaling/technical_decisions_system.md](../Context_Scaling/technical_decisions_system.md).

```
technical_decisions/
├── README.md             ← this file
├── history/              ← one file per significant design decision (event log)
├── tech_debt/            ← one file per known deferred work item
└── incident_history/     ← one file per notable bug / post-mortem
```

When an incident produces a lasting constraint, that constraint must also be surfaced in the base [../technical_decisions.md](../technical_decisions.md) summary so it is always in context.
