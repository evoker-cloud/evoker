# Standalone CLI

The public engine and Evoker Cloud use the same ARTEX-derived core. The CLI will
provide the local orchestration needed to run that core outside Evoker Cloud.

1. `evoker init`: write a scope file and model-provider configuration. Store
   credentials outside assessment plans and outside the worker container.
2. `evoker assess`: validate explicit scope, start an ephemeral isolated runtime,
   and operate its model/inspection mailbox through a local trusted broker.
3. `evoker report`: export stored events and findings as Markdown or JSON.
4. Accept configurable OpenAI-compatible endpoints, including local model
   servers. Route through the broker so provider credentials never reach the
   agent process. Preserve the hosted transport's origin restrictions.
5. Persist bounded events and evidence outside disposable worker storage. Stop
   on cancellation, deadline, model budget, or provider failure; remove the
   runtime and per-run database in every terminal path.
6. Test provider tool-call compatibility, context limits, network scope,
   cancellation, container limits, and cleanup with a local controlled fixture.

Start with the current read-only inspection profile. Add intrusive test types
only with explicit scope controls and independent runtime enforcement. Do not
replace ARTEX's planner or agent system with a second orchestration framework.

Acceptance: a user can clone a release, configure their own compatible model,
run against a controlled authorized target, export a report, and verify that
no worker or database remains running. No Evoker Cloud account is required for
that path. Using the Evoker API is an optional provider choice.
