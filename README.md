# TestForge

Generate C++ test code from markdown test plans.

```
markdown plan  ->  IR (TestCase/TestStep)  ->  code fragments  ->  assembled C++
```

The two contracts that matter are the **IR** (what a plan means) and the
**device manifest** (how one target turns that meaning into files). Everything
else is replaceable.

## Quick start

```bash
pip install -e '.[dev]'

testforge devices                                     # what can be generated for
testforge parse examples/sensor_init.md               # what TestForge reads
testforge generate examples/sensor_init.md \
    --device example_device --case 1 -o ./out         # write the files
testforge serve                                       # REST API, docs at /docs
```

Running `generate` into the same `-o` directory again regenerates in place:
only the regions between the anchor markers are rewritten, so anything you
wrote by hand around them is kept.

## Design rules

**Determinism.** The same input produces byte-identical output. No timestamps,
no random ids in generated code. Golden-file tests depend on it, and so does a
reviewable `git diff` when generated files are committed.

**Diagnostics, not errors.** Plans are written by hand and are reliably messy.
Recoverable problems come back in a `diagnostics` array with HTTP 200 so the
author sees every issue at once. Only a plan that yields no usable case is a
4xx — and its body carries the same `diagnostics` shape, so one rendering path
handles both. Branch on `code`, never on `message`.

**Statelessness.** Nothing is stored between requests. To regenerate a file,
the client sends its current content in `existing_files` and gets it back with
only the anchored regions rewritten. The state lives with whoever owns the file.

**Layer direction.** `api/` and `web/` both depend on `service`, never on each
other, and the web layer never re-enters the application over HTTP.

**DTOs are not the IR.** `api/schemas/` is the published contract;
`core/models.py` is internal and free to grow. `api/mappers.py` is the only
place that knows both.

## Layout

```
src/testforge/
  core/              pure logic, zero web dependencies
    models.py        the IR: TestCase, TestStep, CodeFragment, GeneratedArtifact
    parser.py        markdown -> IR, via markdown-it token stream
    naming.py        step title -> C++ identifier
    assembler.py     anchor-based injection
    templating.py    Jinja2 environment and filters
  devices/
    manifest.py      the manifest schema, validated at load time
    registry.py      discovery and lookup
    builtin/         devices shipped with the package
  service.py         GenerationService: the only orchestrator
  api/               FastAPI: schemas, routers, mappers, error mapping
  cli.py             a second consumer, which keeps core honest
```

## REST API

Base path `/api/v1`. Interactive docs at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness and device count |
| GET | `/devices` | list devices |
| GET | `/devices/{id}` | anchors, naming pattern, output patterns |
| POST | `/parse` | plan -> IR + diagnostics, no device needed, no code |
| POST | `/generations` | plan + device -> artifacts |

`/parse` exists separately so a UI can preview steps as they are typed, and so
format errors surface before a device is even chosen.

`POST /generations` is a plural noun rather than `/generate` because the thing
being created is a generation. That leaves room to return `202` + polling if a
compile check is ever added, and to add `GET /generations/{id}` if results are
ever persisted — without moving the URL.

`generation_id` is a correlation id for logs. Nothing is stored; it cannot be
fetched.

### Response representations

```
POST /api/v1/generations?format=json   application/json  (default)
POST /api/v1/generations?format=zip    application/zip   + Content-Disposition
POST /api/v1/generations?format=file   text/plain        single artifact only
```

A query parameter rather than `Accept` negotiation, because a plain HTML form
cannot set `Accept`, and this way a form post triggers a browser download with
no JavaScript at all.

### Status codes

| Code | Meaning |
|---|---|
| 400 | body does not match the schema, or a bad naming pattern |
| 404 | unknown `device_id` |
| 413 | `source` over the size limit |
| 422 | plan yields no usable case, or `existing_files` is missing anchors |
| 500 | broken manifest or template — our fault, details are logged not returned |

Anchor problems are 422 rather than 409: it is "this input cannot be used", not
a concurrency conflict a client should retry.

Every 4xx/5xx body is the same envelope:

```json
{
  "error": { "code": "device_not_found", "message": "...", "details": {} },
  "diagnostics": []
}
```

## The plan format

```markdown
# Test Case: Sensor Initialization Sequence

- ID: TC-001
- Device: example_device

Optional prose describing the case.

## Step 1: Power on the device

Drive the enable line high and wait for the regulator to settle.

**Expected:** The READY flag is asserted within 500 ms.
```

* `# Test Case: <title>` starts a case; several per document is fine, and each
  produces its own artifacts.
* A bullet list directly under the heading is metadata (`Key: Value`).
* `## Step N: <title>` starts a step. Both `Step` and the number are optional;
  steps are indexed by position, and a mismatch raises
  `step.index_mismatch` rather than renumbering silently.
* `Expected:`, `**Expected:**`, `Expected result:` and `預期結果：` all open an
  expectation paragraph.
* Step bodies keep their raw markdown, fenced code blocks included. A `#`
  inside a fence is never mistaken for a heading.

Heading levels are configurable per device, so a team can keep its existing
layout instead of rewriting its plans.

## Adding a device

Copy `src/testforge/devices/builtin/example_device/` and edit it. No Python
changes. Devices are also picked up from `./devices/` and from
`TESTFORGE_DEVICE_PATH`; a later root shadows an earlier one, so a project can
override a builtin device.

```
my_device/
  manifest.yaml
  templates/
    test_case.h.j2       # skeleton, carries the anchor markers
    test_case.cpp.j2
    step_decls.cpp.j2    # fragment rendered into one anchor
    step_calls.cpp.j2
    step_defs.cpp.j2
```

The manifest declares the anchor spelling, the naming pattern, and which
fragment fills which anchor in which file. `example_device/manifest.yaml`
documents the full template context inline. Every manifest is validated when
the registry loads, so a typo stops the service from starting rather than
failing someone's first request.

`example_device/support/testforge_runtime.h` is a reference runtime, not part of
generation. It exists so the generated code compiles and runs as-is:

```bash
testforge generate examples/sensor_init.md -d example_device --case 1 -o /tmp/tf
cp src/testforge/devices/builtin/example_device/support/testforge_runtime.h /tmp/tf
# add a main() that calls example_device::RunSensorInitializationSequence(ctx)
g++ -std=c++17 -Wall -Wextra -Werror -o runner main.cpp test_*.cpp
```

## Tests

```bash
pytest                                              # all of it
UPDATE_GOLDEN=1 pytest tests/test_golden.py         # accept template changes
```

Three layers: unit tests for the edge cases (naming, parsing, anchors), golden
files for what a user actually receives, and API tests for the contract —
status codes, the error envelope, and the regeneration round trip.
