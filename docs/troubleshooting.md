# Troubleshooting

**`docker` is not recognized:** install Docker Desktop, enable WSL 2 / Linux containers, start Docker Desktop, and reopen PowerShell. Check `docker version` and `docker compose version`.

**Startup still connecting:** run `docker compose ps -a` and `docker compose logs init api mongo-usa`. Initialization can take a minute. An exited initializer with code 0 is expected. After correcting a failed initializer, run `docker compose up --build -d`.

**Port 3000 is in use:** stop the other local service, or change the host port to `127.0.0.1:3001:80` and browse that port. MongoDB has no host ports to conflict.

**Network overlaps:** change the subnet and the three static addresses in `compose.yaml`, and change the matching table in `infra/agent/agent.py`. Rebuild. Do not change only one side.

**No writable primary after jamming:** use Network Jammer → Restore All Links. Watch the notebook for PRIMARY and two SECONDARY members, then retry your original pending request ID. Allow 20–40 seconds. A minority may show a former primary until election/heartbeat detection completes; it still cannot acknowledge majority writes.

**API unavailable after a container was recreated:** network namespace sharing ties regional APIs and agents to the database container instance. Run `docker compose up -d --force-recreate` to recreate the full stack without deleting volumes. Reapply or restore firewall state as appropriate.

**Firewall agent fails:** inspect `docker compose logs agent-usa agent-france agent-australia`. The images require Linux iptables and the Compose NET_ADMIN capability. Do not move the firewall commands to the host. Retry Restore All after fixing agents.

**A transaction timed out:** open the ATM and use Check Result. If absent, use Retry Same ID. Do not discard the ID and submit a replacement unless the first operation is definitively rejected or reconciled. Restoring connectivity is necessary before reconciling an isolated region.

**Live test failed:** the test result contains the failed assertion or HTTP error. Restore all links, wait for replica recovery, and run again with no other user interacting. Reset data if a failed stress test left Ethan without test funds. The integration suite intentionally resets demo data before running.

**Offline startup attempts downloads:** first complete `docker compose up --build -d` with internet access. Keep the built images; use `docker compose up -d` while offline. Rebuilding images may require package registry access even when the application itself has no internet dependencies.

**Need to inspect database directly:** `docker compose exec mongo-usa mongosh --quiet --eval 'rs.status()'`. This is diagnostic access from inside the lab, not a browser banking route.
