# Security policy

## Supported versions

Only the latest 0.1.x release receives security fixes.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private vulnerability reporting for this
repository (Security tab, "Report a vulnerability"). Include steps to reproduce and the impact.
You can expect an acknowledgement; there is no guaranteed response time for this volunteer project.

## Scope and privacy model

EnvMirror runs locally, makes no network requests and sends no telemetry. Areas of interest:
secrets leaking into snapshots, unsafe handling of untrusted snapshot files (parsing, HTML
or terminal output), and subprocess handling. Redaction is heuristic and cannot guarantee that no
sensitive value survives; see the README's Privacy and security section. This project has not
had an independent security audit.
