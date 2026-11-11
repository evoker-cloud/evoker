# Runtime interface

`engine/cmd/evoker` is the supported engine entrypoint. The original ARTEX web
application is retained in the source snapshot for completeness and is not
built or started by this entrypoint.

The plan contains `objective`, optional `context`, exact `hosts`, and a Unix
millisecond `deadline`. The current implementation accepts one to three hosts
and a deadline within fifteen minutes. It creates the agent workflow in its
private database, emits `ready`, then waits for `activate` on stdin.

The supervisor in `engine/evoker-port/runtime/supervisor.py` starts PostgreSQL on
a private Unix socket and the engine as an unprivileged process. Its mailbox
listens on loopback only. An external controller uses the fixed `configure`,
`activate`, `poll`, and `reply` operations through the sandbox execution channel.
Model requests and fixed inspection operations leave the sandbox through this
mailbox; the worker has no direct network access or provider credentials.

The model broker supplies OpenAI Chat Completions responses with verified token
usage. Requests carry agent-role and operation identifiers. Inspection replies
contain bounded evidence from authorized hosts. The broker must validate exact
scope, DNS resolution, redirects, destinations, request rates, and deadlines
independently of the engine.

The container needs a read-only root filesystem, UID/GID 1000, no capabilities,
no privilege escalation, no host mounts, no service-account token, default-deny
network policy, bounded writable scratch, CPU/RAM limits, and a separate deadline
watchdog. Reference limits are one CPU, 2 GiB RAM, 256 MiB scratch, one worker,
and fifteen minutes. An ordinary unsandboxed process is not equivalent.

Normalized events cover lifecycle state, activity summaries, roles, and findings.
Do not expose private model reasoning or raw tool output as customer activity.
The controller must persist events, drain pending operations, terminate the
runtime after completion or cancellation, and verify cleanup.

The exact source snapshot is fingerprinted by `engine/SOURCE-FILES.json`.
`engine/evoker-port/runtime-image.json` identifies the historical tested image;
that local image reference is not a public download. The build recipe includes
the source inputs required to construct the runtime.
