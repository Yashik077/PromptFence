# Security policy

## Reporting a vulnerability in PromptFence

Use GitHub's private vulnerability reporting on this repository
("Security" → "Report a vulnerability"). Please do not open a public issue for
a vulnerability in the tool itself.

Include:

- the affected version or commit,
- a minimal reproduction, ideally as a scenario file or a failing test,
- what an attacker gains,
- any logs with keys and secrets removed.

**There is no guaranteed response time and no promised turnaround.** This is a
small project maintained in spare time; treat the channel as best-effort. If a
report is time-sensitive, say so in the first line.

Do not include real credentials, private user data, or a working exploit against
a third-party system. Report those to whoever owns that system.

## What PromptFence is and is not

PromptFence is a testing aid. It runs scenarios against a synthetic application
you can inspect in full, and it reports what that application permitted.

It does not:

- prove an AI application is secure,
- replace authorization, secure design, code review or penetration testing,
- prove the absence of prompt injection,
- certify any model.

A clean run means the tested configuration held the tested invariants for the
tested scenarios. That is the whole claim.

## Safe defaults

- The `mock` adapter makes no network requests and needs no credentials.
- Scenario files are parsed with `yaml.safe_load`. No Python is imported,
  evaluated or executed from a scenario, and there is no field that names a path
  to write or a command to run.
- The mock application's tools have no filesystem, network or process access.
- Untrusted text is escaped before it reaches an HTML report.
- The OpenAI-compatible adapter is opt-in, refuses to start without an explicit
  endpoint and model, and keeps the API key out of results, reports and
  `repr`.
- Credentials are read from the environment. There is no `.env` in this
  repository.

## Network behaviour

Running with `--model mock` is fully offline.

Running with `--model openai_compatible` sends the conversation — including
scenario input, retrieved text and tool results — to the configured endpoint.
The CLI prints the endpoint before the run starts. Use synthetic scenarios when
you do that. Scenario content is not scrubbed before it is sent.

## Data retention

Results contain scenario ids and versions, event records, metrics, error strings
and, unless you remove it, the model's final output. Built-in scenarios are
synthetic, so this is harmless out of the box. If you point PromptFence at your
own application, review the output before committing it: `results/` is in
`.gitignore`, but `-f` will override that.

Generated reports should never be committed. They are evidence about one run of
one configuration, and a stale one is worse than none.

## Responsible use

Run these tests only against systems you own or have explicit permission to
assess. The bundled sandbox is designed to demonstrate AI security failures
without touching anything real.
