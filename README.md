# Global Bank Tester

A local pixel-art airport adventure backed by a real three-member MongoDB replica set. Travel between New York, Paris, and Sydney; use an ATM; inspect each replica; partition a node and watch elections and recovery.

## Run on Windows

For a double-click launch:

1. Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/), use its WSL 2 / Linux-container backend, and complete its initial setup. Restart Windows if requested. This is a one-time requirement; Python and Node are not needed on your computer.
2. Double-click **Start Bank.cmd** in this folder. It starts Docker if necessary, builds and starts the application, waits for the databases and controls, then opens your browser. The first launch needs internet access and can take several minutes.
3. Double-click **Stop Bank.cmd** when finished. Saved balances and history are preserved. Closing the browser alone leaves the lab running.

The launcher reports setup or startup errors in its window and keeps failed launches visible. Its complete startup path still requires verification with Docker Desktop installed.

To start manually instead:

Install Docker Desktop with the Linux-container / WSL 2 backend and start it. From this directory:

```powershell
docker compose up --build -d
docker compose logs -f init api
```

Open **http://localhost:3000** once initialization finishes. The first build downloads container images and dependencies. Subsequent runs work offline with those images and volumes available. No remote fonts, images, APIs, or cloud services are used at runtime.

The initial primary is normally USA (higher priority); the actual elected primary is always discovered. Initialization is idempotent. Seeded balances: Alice $1,000; Bob $2,500; Charlie $750; Diana $5,000; Ethan $200. Currency is USD in every country.

```powershell
docker compose down           # stop, preserve balances and transaction history
docker compose up -d          # resume
```

Use Jammer → Reset demonstration data → Prepare reset → Confirm to explicitly replace account data and restore links. This deletes demonstration transaction history. Resolve pending requests before resetting. Normal restarts never reseed existing accounts.

## Explore

1. Click the ATM, select Alice, and deposit $100. The receipt identifies the actual committing primary and original region. Print creates a local browser receipt.
2. Open the notebook and compare Alice's local balance across all three instances. Travel to Paris and check the authoritative balance at its ATM.
3. Arm the jammer, isolate Australia, then deposit in a majority region. The isolated replica remains inspectable and stops receiving updates. Its ATM refuses banking.
4. Restore all links. Observe actual replica convergence in the notebook.
5. Identify the current primary in the notebook, isolate it, and observe the other two members elect a primary. Banking in the majority resumes after election. Restore connectivity.
6. Use Guided Tests to run six live demonstrations with pass/fail assertions. Tests change real demo data: tests 1–5 deposit $1; test 6 temporarily withdraws Ethan's balance and restores it on success. Avoid concurrent manual activity while testing.

## Verify

The live integration suite resets demonstration data, checks input validation, overdraft protection, cross-region idempotency, and all six scenarios:

```powershell
docker compose exec -T api python integration_check.py
```

Allow several minutes for elections and recovery. A failed concurrent-withdrawal demonstration can leave Ethan's balance changed; inspect history and explicitly reset demo data before repeating.

For contract tests on a host with Python 3.11+:

```powershell
python -m pip install -r backend/requirements.txt
python -m unittest discover -s tests -v
```

Frontend development with Node.js 22+:

```powershell
cd frontend
npm install
npm run build
```

For a frontend dev server, expose the API deliberately through a local development proxy; the default Compose setup publishes only Nginx at port 3000. Prefer the Compose build for the complete application.

## Database interpretation

This application runs **three database instances containing one replicated logical database** (`bank`). Accounts and financial writes are shared through a replica set. It does not provide three independent datasets. Confirm that this interpretation meets the course's “three databases” criterion before presenting it.

## Architecture and limits

See [architecture](docs/architecture.md) for networking, consistency, partition mechanics, security boundaries, and implementation tradeoffs, and [troubleshooting](docs/troubleshooting.md) for recovery instructions.

This is a classroom lab with unauthenticated MongoDB on a private Docker network. Only the web interface is published, bound to `127.0.0.1`. Do not deploy this Compose stack to a public server. The administrative agent token is internal; it is absent from frontend code. NET_ADMIN is granted only to the three network agents. No Docker socket is mounted.

Optional controlled replication delay is not implemented. The notebook reports actual operation positions and balances without inventing lag values. Its observation log is session memory, not a durable audit log; financial history is persisted in MongoDB. Monitoring samples nodes independently, so the display is not a globally atomic snapshot. Very brief election states can occur between samples.

## Verification record

See [verification](docs/verification.md). The source includes executable checks; a live Docker run is required before claiming distributed behavior has passed.
