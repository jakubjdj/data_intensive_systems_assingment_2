# Implementation architecture

## Components and repository

`frontend/`: React, TypeScript, Vite, Tailwind and local Canvas pixel artwork. Nginx serves the production build and proxies `/api`. There is no client-side financial simulation.

`backend/region.py`: one FastAPI process per airport, with a MongoDB replica-set client. Financial requests execute in that region's actual network namespace.

`backend/control.py`: same-origin gateway, node inspection, event observations, reset, and firewall orchestration. Its separate control-network access remains available during database partitions. It never performs ordinary user financial operations through its unrestricted cluster connection; that connection is reserved for initialization/reset.

`infra/agent/`: narrowly scoped firewall controller. Each agent shares its database network namespace, has NET_ADMIN, and can only change fixed peer rules through its API. The gateway calls it with an internal token.

`backend/initialize.py`: idempotent replica-set initialization and transactional seed.

`backend/scenarios.py`, `backend/integration_check.py`, `tests/`: six executable demonstrations, full-stack verification, and contract tests.

## Docker topology

The dedicated `172.29.83.0/24` bridge uses stable database addresses:

| Region | Replica address | Regional API | Firewall agent |
| --- | --- | --- | --- |
| USA | mongo-usa:27017 / .11 | same namespace :8001 | same namespace :8002 |
| France | mongo-france:27017 / .12 | same namespace :8001 | same namespace :8002 |
| Australia | mongo-australia:27017 / .13 | same namespace :8001 | same namespace :8002 |

The replica configuration advertises Docker DNS names, resolvable by every member and regional backend. The browser never resolves these names or connects to MongoDB directly. Each MongoDB has its own persistent volume. A one-shot initializer waits for all three health checks and a writable majority before committing seed data. Dependent APIs start afterwards.

Only `127.0.0.1:3000` is published. Nginx → gateway → selected regional API → discovered MongoDB primary is the banking path. Gateway → individual MongoDB is the inspection path. Gateway → firewall agent is the control path.

## Real partitions and regional routing

The firewall agent inserts `GB_INPUT` / `GB_OUTPUT` chains before other namespace rules. Isolation drops incoming traffic from and outgoing traffic to the other two database IPs. Existing replication streams are affected as well as new connections. A member process stays running and keeps its existing data; this is not container shutdown.

Because a region's bank API shares its member's network namespace, it cannot discover or contact majority members around the partition. The gateway additionally queries actual agent rules and refuses banking from a component smaller than two. If rule state cannot be established, it fails closed. It does not maintain an independent boolean pretending to be network state. Multiple isolated nodes are supported; there is no writable majority when all nodes are disconnected.

The gateway uses a distinct Docker address, so inspection and agent HTTP requests are unaffected by peer drops. Restore flushes only this application's two custom chains. No host firewall, Wi-Fi, Docker socket, arbitrary container commands, or unrelated network is exposed.

Firewall updates cover two chains sequentially rather than atomically. Transient failures are surfaced, and partial isolation still blocks peer communication; Restore All retries every agent. Agent restarts preserve existing chains. If a database container is recreated, recreate dependent namespace-sharing services together with `docker compose up -d --force-recreate`.

## Financial correctness

Money uses bounded integer cents. Account updates and immutable transaction records commit together in MongoDB multi-document transactions with snapshot reads and journaled majority write concern. Withdrawals filter on sufficient balance and use `$inc`; concurrent write conflicts retry through the driver transaction helper. Insufficient funds never produce a committed ledger record.

A UUID request ID is the transaction record's unique primary key. Repeated requests return the existing receipt only when the financial payload matches. A different payload using that ID returns 409. Racing duplicates abort/reconcile through the unique key and transaction boundary. Cross-region retries preserve the original receipt and original initiating region.

ATM balance decisions use primary linearizable single-document reads with bounded server execution. Transaction history uses majority reads from the primary. Individual replica inspection intentionally uses direct local reads, which may be stale or include state not yet majority committed. It is labeled accordingly. Account balances displayed together are independent reads rather than one atomic multi-account snapshot.

Driver selection, socket, client operation, and commit timeouts bound ordinary database calls. When a connection fails or a commit acknowledgment is lost, a 503 is treated as an uncertain outcome. The frontend saves the request ID and payload in localStorage before submission, disables new transactions, and offers reconciliation and retry using the same ID. A missing record does not prove that a still-running request cannot commit. Never create a fresh ID to retry an uncertain request. A definitive input/business rejection (4xx) releases the request.

The receipt stores the primary observed by the regional driver while its transaction runs. A write is not labeled successful until the transaction helper returns after majority acknowledgment.

Reset prevents new gateway banking calls, waits for existing proxy requests to finish, restores communication, and transactionally replaces the seed. Do not reset during unresolved transaction outcomes: a timed-out proxy request may have outlived its HTTP connection. Use reset only as an explicit fresh-demo operation.

## Observability and tests

Role, peer health, optime, and last applied timestamps come from `hello` and `replSetGetStatus`; balances/history come from direct reads. No fabricated lag, roles, or financial results are displayed. Firewall links come from agent rule inspection, while peer health is reported separately because heartbeats lag rule changes. The field notebook logs observed transitions and transaction acknowledgments; retries may log an acknowledgment again for the same ID.

Tests cover deterministic seed, strict amounts, overdrafts, duplicate and conflicting IDs, majority/minority behavior, genuine stale local state during isolation, primary failover, convergence, and simultaneous full-balance withdrawals. Guided tests check real results and restore connectivity in a finally block. They are demonstrations of different objectives, with common partition checks shared by tests 2–5.

## Technical risks and local security

The proposed subnet may conflict with an existing VPN or Docker network. Change both Compose addresses and the agent's fixed peer table together if necessary. NET_ADMIN and Linux iptables require Docker Desktop Linux containers. First-start elections and later priority takeovers take time. Persistent partitions can survive application restarts; Restore All is always available unless an agent/container fails.

The lab has no user authentication and must remain on loopback. Administrative POSTs require a custom header and matching Origin when supplied; browsers cannot issue cross-origin simple form writes to these endpoints. Internal service calls require the token. This is a local educational boundary, not production bank security or protection from other containers intentionally attached to the same network. No credentials or live customer data should be used.
