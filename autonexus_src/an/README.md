# AUTONEXUS AI 2.0

AUTONEXUS is an offline-first prototype for dealership inventory recovery and
operations visualization. It combines a FastAPI service, CSV-backed planning,
a one-page operations dashboard, and a Three.js Living World.

> **Data and live-feed limitation:** the CSV files currently in `data/` are
> generated fictional sample data. They are not dealership telemetry. The app
> does not currently have a working external telemetry connector, and it does
> not make live routing, LLM, ERP, DMS, or inventory-write calls. The dashboards
> label the source and show the CSV file refresh time. Do not mark the sample
> CSVs as operational data.

## Contents

- [Quick start](#quick-start)
- [Configuration and owner access](#configuration-and-owner-access)
- [Application pages](#application-pages)
- [Data model and refresh behavior](#data-model-and-refresh-behavior)
- [Living World workflow](#living-world-workflow)
- [Voice input](#voice-input)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Build and test](#build-and-test)
- [Security and limitations](#security-and-limitations)

## Quick start

Use Python 3.12 for the project environment. Run commands from this `an/`
directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure `.env` as described below, then start the application:

```powershell
python -m uvicorn autonexus.api:app --host 127.0.0.1 --port 8765 --reload
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) for the operations
dashboard. Other pages are linked from the dashboard or available at
`/world`, `/site`, `/ui/index.html`, `/ui/twin.html`, and `/ui/twin3d.html`.

The checked-in/current `data/*.csv` files are used as-is. The app and build
scripts do **not** create or regenerate CSV data when a file is missing; a
missing or invalid required dataset fails explicitly.

## Configuration and owner access

`.env` is local configuration and must not be committed. Never put credentials
in Python, HTML, JavaScript, README text, or generated files.

1. Generate a random JWT signing secret, at least 32 characters long:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Put the result in `JWT_SECRET` in `.env`.
2. Set `OWNER_EMAIL` to the sole owner account email.
3. Generate a PBKDF2 password hash from a hidden password prompt:

   ```powershell
   python -c "import getpass; from autonexus.auth import hash_pw; print(hash_pw(getpass.getpass('Owner password: ')))"
   ```

   Copy the resulting hash into `OWNER_PASSWORD_HASH`. Do not put the password
   itself in `.env`.
4. Restart the server after changing `.env`. `/config/status` reports only
   whether owner authentication is configured; it never returns the secret or
   password hash.

The configured owner is the only account that can approve/reject Living World
transfers or use other protected approval endpoints. The API accepts a JSON
login body containing an email and password, and returns a short-lived signed
bearer token. The browser keeps that token in session storage for the current
tab session. There are no built-in demo-user credentials or authentication
fallbacks. If owner credentials are not configured, login and privileged
actions remain unavailable.

Set `DATA_PROVENANCE=synthetic` while using the included generated CSVs. Change
it to `operational` only after replacing them with a verified operational
dataset. This label is a declaration, not a way to validate data origin.
Optional provider settings in `.env.example` are feature flags/configuration
hooks; they do not imply that a provider integration is implemented.

## Application pages

### Operations dashboard — `/`

A single scrolling cockpit with section links for overview, inventory, route
network, workshop, suppliers, demand/intelligence, security, and operations
tools. It renders dataset values as readable labels, charts, cards, and tables;
it does not expose raw API response JSON in the page.

The dashboard requests `/dashboard/data` on load and every 30 seconds. It
reports the source label and the newest relevant CSV modification time. The
route, inventory, repair, bay, supplier, delivery, demand, and security
visualizations are aggregated from the current CSV files. The Living World
phase and scenario summary are fetched separately.

The dashboard also includes:

- route planning and road-closure comparison;
- dataset-populated route destination and part controls, with optional custom
  quantity and road closure on a segment from the selected planned route;
- agent, security, audit, what-if, and demo controls;
- owner sign-in and protected approval/audit controls;
- local registration/insurance document checks and a review-before-save lot-walk assistant;
- synthetic federated-learning and evaluation visualizations.

These are prototype operations and simulations; they do not write to a live
dealership system.

### Living World — `/world`

The WebSocket-driven Three.js experience has seven scenes: Overview,
Inventory, Suppliers, CyberShield, Scheduling, Route, and Federated. It
refreshes world state over `/ws/world` (with REST polling as a connectivity
fallback), and includes:

- destination dealership, part, required quantity, and optional source inputs
  populated from the CSV dataset;
- automatic required quantity from matching repair-order demand when the
  quantity field is left blank;
- route, inventory, supplier-policy, security-event, technician, and bay
  context from the current dataset;
- a transfer approval checkpoint; the vehicle does not leave and inventory
  does not change until the configured owner approves;
- a road-closure control during travel, causing the backend planner to
  recalculate when an alternative route exists;
- a WebGL-free 2D text fallback and reduced-motion support.

The world is an in-memory simulation. Its transfer changes the simulation's
planner state only; it does not modify the source CSVs or an external inventory
system. Resetting/reconfiguring reloads the CSV dataset.

### Visual site and labs — `/site`, `/ui/*`

`/site` is a visual, animated introduction and dataset-backed network/service
floor. It refreshes its CSV-derived status and route snapshot every 30 seconds
when served by the application. `/ui/index.html` compares Dijkstra and A*
against the current road-network CSV. `/ui/twin.html` and `/ui/twin3d.html`
are generated visual route demonstrations. Run the build scripts after
editing their templates or source modules.

## Data model and refresh behavior

The 19 CSVs in `data/` are:

| File | Purpose |
|---|---|
| `dealerships.csv` | Dealership identifiers, names, and coordinates |
| `warehouses.csv` | Warehouse identifiers, names, capacities, and coordinates |
| `parts.csv` | Part catalog and compatibility fields |
| `inventory.csv` | Part quantities by dealership/warehouse |
| `repair_orders.csv` | Repair demand, priority, status, and assignments |
| `technicians.csv` | Dealership, skill, shift, and availability |
| `service_bays.csv` | Service bay availability by dealership |
| `appointments.csv` | Repair-order and bay appointment relationships |
| `suppliers.csv` | Supplier reliability, lead time, and restriction status |
| `quotations.csv` | Supplier quotes by part |
| `purchase_orders.csv` | Purchase order quantities and values |
| `deliveries.csv` | Delivery status and ETA records |
| `inventory_movements.csv` | Historical inter-site movement records |
| `road_network.csv` | Road edges, travel cost, and travel time |
| `historical_demand.csv` | Demand history and simulated stockout labels |
| `security_events.csv` | Security-event records and sample attack labels |
| `procurement_policies.csv` | Procurement policy limits and rules |
| `vehicle_records.csv` | Vehicle records used by repair orders |
| `documents.csv` | Sample document references and statuses |

`autonexus.telemetry` loads the planner's required tables, checks core
references and numeric values, and builds the planner database. The
`/dashboard/data` endpoint reads the current CSVs for every request. The
Living World loads them on startup and again when reset or configured. Its
WebSocket then streams its in-memory simulation state; it does not reread the
files on every animation frame.

The dashboard's 30-second refresh interval is a UI polling interval, not a
claim that the source is live. A verified external feed requires a valid
read-only HTTPS endpoint, a response schema, authentication method, and an
explicit polling policy. No external provider endpoint/schema is configured in
this project, so no network request is made to an assumed or placeholder URL.
The local mock endpoint below is only a connector test fixture. Until a real
provider adapter is implemented and validated, use the CSV directory and keep
the provenance label accurate.

For connector development, `GET /mock/telemetry/v1/snapshot` exposes the same
CSV-derived aggregates in a stable, read-only response envelope. It always
identifies itself as `SYNTHETIC MOCK TELEMETRY`, reports
`source.external_feed_status` as `mock_only`, and includes a schema version.
This endpoint is a local test fixture, not an external provider, live
dealership data, or a replacement for a real telemetry adapter. It performs
no writes.

To explicitly regenerate the fictional development dataset (this overwrites
the CSVs), run:

```powershell
python -m autonexus.gen_csv
```

This is a manual developer action only. Neither server startup nor a build
script runs it automatically.

## Living World workflow

1. Select a destination and part from the values exposed by `/world/state`.
2. Leave required quantity blank to use repair-order demand, or enter a
   positive custom quantity. Optionally select a specific source site.
3. Apply the inputs. The backend validates every selection against the loaded
   dataset and reports on-hand stock and shortage.
4. Press **Start**. The simulation computes feasible sources/routes, supplier
   checks, security risk, procurement policy, and scheduling context.
5. At **Awaiting owner approval**, the transfer is held. Sign in from the
   dashboard's Security section, return to `/world`, then approve or reject.
6. During transit, **Close road ahead** blocks a network edge. The backend
   replans around it when possible; if no path exists the simulation stalls.
7. Inventory is updated in the in-memory simulation only after arrival; the
   workflow then assigns compatible available technicians/bays and verifies
   shortage recovery and the audit chain.

Invalid input, no feasible source, no alternate route, unauthorized decisions,
and inactive journey controls are returned as explicit API errors and surfaced
in the UI.

## Voice input

The Voice First Lot Walk panel records audio in the browser and posts the WAV to
`POST /voice/transcribe` on this same local server. A local faster-whisper model
detects the spoken language; audio does not go to a cloud provider. Set
`WHISPER_MODEL_PATH` to the local multilingual model directory. Speech is
transcribed for review, then `POST /vehicles/lot-walk/preview` extracts the
vehicle, lot location, condition, and status. **Confirm & Save** requires owner
sign-in and appends the observation to SQLite; `/api/v1/vehicles` returns the
latest observation. English, Hindi, and Bengali lot/location words are handled
by the local rule parser, but the vehicle ID and bay/row code should be spoken
clearly and the extracted result should always be reviewed.

The Smart Document Extraction panel accepts multiple PDFs or images and
validates them together against the selected local vehicle. Text PDFs are
extracted locally with PyMuPDF. Scanned PDFs and image files use local
Tesseract; configure `TESSERACT_CMD` or add the executable to PATH. The checks
cover required fields, West Bengal registration-mark format, policy dates, and
cross-document/local-VIN consistency. They are human-review checks, not an
official registration lookup or deal-finalization approval. Neither feature
calls a third-party API.

## API reference

### Status and dataset

| Method and path | Purpose |
|---|---|
| `GET /health` | Service health |
| `GET /state` | Current high-level orchestration and audit status |
| `GET /config/status` | Safe booleans for optional integrations and owner setup |
| `GET /dashboard/data` | Current CSV-derived dashboard aggregates and provenance |
| `GET /mock/telemetry/v1/snapshot` | Read-only CSV-backed mock response for connector testing; always labeled synthetic |
| `GET /federated` | Federated-learning result |
| `GET /world/federated` | World federated-learning summary |
| `GET /audit/verify` | Verify in-memory audit-chain integrity |

### Planning and operations

| Method and path | Purpose |
|---|---|
| `POST /recovery/plan` | Plan a part transfer; accepts optional `dealer`, `part`, `required_qty`, and repeated `blocked` query values |
| `POST /recovery/execute` | Execute a planned transfer; requires owner bearer authentication |
| `POST /agents/run` | Run the agent workflow; accepts optional dealer, part, and blocked edges |
| `POST /agents/approve` | Approve the agent workflow; requires owner bearer authentication |
| `GET /whatif/{n}` | Run a what-if case |
| `GET /evaluation` | Run the modelled evaluation comparison |
| `GET /ml/evaluate` | Evaluate the synthetic ML dataset |
| `GET /simulate/bays` | Run the service-bay simulation |
| `GET /security/simulate` | Run the isolated CyberShield simulation |

### Living World

| Method and path | Purpose |
|---|---|
| `GET /world/state` | Current state and dataset-driven input options |
| `POST /world/configure` | Set destination, part, optional `required_qty`, and optional source |
| `POST /world/start` | Start a feasible shortage simulation |
| `POST /world/block` | Close the road edge currently ahead of the simulated vehicle |
| `POST /world/reset` | Reset simulation state |
| `POST /world/approve` | Approve a pending transfer; requires owner bearer authentication |
| `POST /world/reject` | Reject a pending transfer; requires owner bearer authentication |
| `GET /world` | Living World page |
| `WS /ws/world` | Live simulation-state stream |

### Security, voice, documents, and pages

| Method and path | Purpose |
|---|---|
| `POST /auth/login` | JSON body `{ "email": "...", "password": "..." }`; returns owner token |
| `POST /secure/approve` | Approve the agent workflow; requires owner bearer authentication |
| `GET /secure/audit` | Read audit records; requires owner bearer authentication |
| `POST /voice/parse` | Parse a submitted text instruction; does not mutate inventory |
| `POST /documents/extract` | Extract structured fields from submitted document text |
| `POST /ocr` | Extract text/fields from an uploaded image; requires OCR dependencies |
| `GET /copilot?q=...` | Ask the local rule-routed operations assistant |
| `POST /demo/{cmd}` | Control the in-memory guided demo |
| `WS /ws` | One-shot orchestration/audit status |
| `GET /` | Operations dashboard |
| `GET /site` | Visual introduction |
| `GET /ui/{name}` | Static UI/lab page |

Protected operations require an `Authorization: Bearer <token>` header. The
token is checked for its signature, expiry, configured owner subject, and
administrator role.

## Project structure

```text
an/
  autonexus/
    api.py            FastAPI application and HTTP/WebSocket routes
    auth.py           Owner-only password-hash login and signed tokens
    telemetry.py      CSV loading, validation, and planner database
    world.py          In-memory Living World state machine
    algorithms.py     Graph, Dijkstra, A*, and assignment algorithms
    recovery.py       Shortage detection, route planning, and transfer execution
    compliance.py     Supplier checks and role permissions
    audit.py          Hash-chained in-memory audit records
    agents.py         Rule-routed operations workflow
    cybershield.py    Isolated security-event analysis/simulation
    federated.py      Local NumPy FedAvg demonstration
    ml.py             Synthetic demand/model evaluation
    optim.py          Scheduling, assignment, and routing optimizers
    docs.py           Text document extraction
    ocr.py            Optional image OCR integration
    voice.py          Text instruction parsing and guarded apply helper
    db.py             Optional SQLite persistence helpers
    demo.py           Guided in-memory demo workflow
    drift.py          Drift metrics
    evaluation.py     Modelled baseline comparison
    rag.py            Local retrieval/relationship helpers
    simbays.py        Service-bay simulation
    adapters.py       Mock adapter interfaces
    gen_csv.py        Explicit fictional CSV generator
    whatif.py         What-if cases
  data/               CSV dataset; currently fictional sample data
  ui/
    dashboard.html    Unified operations dashboard
    world_template.html
    world_src/        Living World scene and state-rendering modules
    site_template.html
    template.html     Dijkstra/A* lab
    twin*_template.html
  build_ui.py         Builds UI pages from current CSVs; does not seed data
  build_site.py       Builds visual site from current CSVs; does not seed data
  tests/              Unit, API, dataset, and Living World tests
```

## Build and test

From `an/`, install and bundle the Motion UI effects, then rebuild generated UI
pages after changing templates or `ui/world_src/*.js`:

```powershell
npm install
npm run build:motion
python build_ui.py
python build_site.py
```

Both builders require a valid existing CSV dataset and fail rather than
silently generating sample records.

Run the test suite:

```powershell
python -m unittest discover -s tests -v
```

The API tests require the packages in `requirements.txt`; OCR tests may also
require a local Tesseract installation. Test outcomes depend on the local
Python/dependency versions and optional system tools.

## Security and limitations

- This is a prototype, not a production dealership system. Use a private,
  trusted network and a strong random JWT secret.
- Keep `.env`, owner password hashes, access tokens, and operational data out
  of source control and logs.
- Authentication uses PBKDF2-HMAC-SHA256 password hashes and one configured
  owner identity. It is not a full identity provider or account-management
  system.
- Audit records are in-memory for the running process unless an explicit
  persistence workflow is used; they are not a tamper-proof external ledger.
- Living World inventory changes are simulation-only and are not written to
  CSV or sent to an external system.
- The included data generator creates fictional locations, events, and
  outcomes. Model accuracy and evaluation improvements are not measured
  dealership outcomes.
- The federated-learning example is educational. It does not provide secure
  aggregation or a differential-privacy guarantee.
- External telemetry ingestion, live road services, ERP/DMS writes, production
  access control, and cloud deployment are not implemented.

## Provenance & dashboard charts (update)
* `GET /integrations/status` lists every integration as LOCAL / SIMULATED / OFFLINE / CONFIGURED / NEEDS_CREDENTIALS. Nothing is probed over the network, so nothing is called LIVE; CONFIGURED means a key is present but untested. Shown in the dashboard's "Data" section.
* Inventory charts: *Units by site* is a column chart; *Highest-volume parts* is a dot-and-stem chart with part names. Every chart now has titled x and y axes.
* **Never share a zip containing `.env`** (it holds API keys and the JWT secret). Rotate any key that has been shared.

## Telemetry feed (synthetic by default)
`GET /telemetry/feed` reads one read-only snapshot and validates schema 1.0 (`autonexus/feed.py`). With `TELEMETRY_URL` unset it uses the built-in synthetic feed and reports SIMULATED. With `TELEMETRY_URL` (+ optional `TELEMETRY_TOKEN`) it makes a real HTTPS call: LIVE only if the call succeeds and validates, otherwise ERROR (no silent fallback). Covered by tests, including a real localhost HTTP round-trip.


## Unified integration update

This build includes the Electric Cobalt AUTONEXUS theme update and a transparent
capability registry. See `docs/integration/INTEGRATION_ARCHITECTURE.md` and
`docs/integration/REPOSITORY_INTEGRATION_MATRIX.md` for the integration
decisions for the separately uploaded reference repositories.

New endpoints:

- `GET /platform/status` — engine modes, dataset provenance and provider configuration.
- `GET /platform/integrations` — integration disposition for each supplied repository.

The integration registry intentionally does not claim that reference repositories
are already running inside AUTONEXUS. Several are alternative applications or
infrastructure stacks. They require compatibility, license, security, data-model
and deployment work before they can become runtime dependencies. Keep the
included sample data labeled synthetic and consult `/platform/status` before
using the system in a real dealership environment.


## Shared operational core (new)
`/command` is the Command Center for the database-backed shortage-to-recovery workflow (`/api/v1`). Create users via the owner account (`POST /api/v1/users`, admin only). See `docs/CORE_ARCHITECTURE.md` for what is and is not implemented.
