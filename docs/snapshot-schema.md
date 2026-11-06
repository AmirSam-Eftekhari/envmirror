# Snapshot schema (version 1.0)

A snapshot is a UTF-8 JSON object. Serialization is deterministic: sorted keys, 2-space indent,
trailing newline. Readers accept a UTF-8 BOM. Files over 8 MB are rejected.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string `"<major>.<minor>"` | Version of this format |
| `envmirror_version` | string | Version of the tool that wrote the file |
| `created_at` | string `YYYY-MM-DDTHH:MM:SSZ` | UTC creation time |
| `system.platform` | string | `Linux`, `Darwin`, `Windows`, ... |
| `system.os_release`, `system.os_version` | string | As reported by Python's `platform` module |
| `system.architecture` | string | Normalized (`x86_64`, `arm64`, `x86`, ...) |
| `system.python_implementation` | string | e.g. `CPython` |
| `system.cpu_count` | integer or null | Logical CPUs |
| `runtimes.<name>` / `tools.<name>` | detection object | `python`, `node`, `npm`, `java`, `rustc` / `git`, `docker` |
| `packages.python` | map name to version | PEP 503 normalized names |
| `packages.node` | object or null | `package_manager`, `dependencies`, `dev_dependencies`, `engines`, `lockfiles` |
| `environment.values` | map | Allow-listed or explicitly opted-in values (redacted) |
| `environment.present` | list | Names whose presence was recorded (never values) |
| `metadata` | object | `scanner_version`, `project_scanned`, `scan_warnings` |

**Detection object:** `status` is `found`, `not_found`, `timeout` or `error`. `found` requires a
`version`. `detail` is a short fixed message (never raw command output).

**Strictness:** all strings are at most 256 characters and may not contain control characters;
collections have size limits; duplicate JSON keys are rejected.

## Evolution policy

- Minor version bump (`1.x`): only adds optional fields. Readers ignore unknown fields and report
  unknown top-level fields as warnings.
- Major version bump: may break compatibility. A reader rejects a major version newer than it
  supports with an actionable message and upgrades older majors via the `MIGRATIONS` registry in
  `envmirror/models/snapshot.py` (empty today because 1 is the first major version).
