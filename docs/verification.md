# Verification

The implementation includes host contract tests and a real full-stack integration runner. A source-only check does not validate MongoDB replication or Docker firewall behavior.

Run live verification after Docker Desktop is installed:

```powershell
docker compose up --build -d
docker compose exec -T api python integration_check.py
```

This modifies and resets demonstration data. Record actual output before claiming the complete acceptance criteria passed.

## Checked on 18 October 2026

- Python compilation passed for the backend, firewall agent, and tests using Python 3.11.0.
- All five contract tests passed, including invalid money/identity inputs, exact receipt timestamp preservation through BSON storage, all eight firewall isolation combinations across three regions, and failure when firewall state is unknown.
- TypeScript checking and the Vite production build passed using Node 22.14.0. The frontend lockfile is included and container builds use `npm ci`.
- Compose YAML parsed successfully; structural checks confirmed 12 services, region/agent network namespace sharing, and no published database ports. This was a YAML check, not Docker Compose validation.

## Not verified in this environment

Docker / Docker Desktop is unavailable. Container builds, Compose startup, actual MongoDB replication, majority transactions, firewall enforcement, elections, recovery, and the live integration suite could not be executed. No browser visual or interaction verification was performed. The six guided demonstrations are implemented but do not have recorded passing results here.

Portable Node and Python dependencies used for source checks were downloaded into ignored `.tools/` in the workspace. They are development aids, not application runtime dependencies.
