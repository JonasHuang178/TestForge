# Spec Delta

## Purpose

Defines the HTTP surface through which clients inspect devices, preview a test
plan and generate code. It is the contract shared by the web interface, the
command line and any automation, so its shapes and status codes are guarantees
rather than implementation detail.

## ADDED Requirements

### Requirement: The API is stateless

The API SHALL NOT retain generated artifacts or request content between
requests. A generation SHALL return its artifacts in the response.

#### Scenario: Nothing is stored

- **WHEN** a generation completes
- **THEN** its artifacts are present in the response body
- **AND** no endpoint exists from which that generation can later be retrieved

### Requirement: Generation identifiers are correlation only

A generation SHALL return an identifier usable for logs and problem reports. The
contract SHALL state that it is not a resource identifier and cannot be fetched.

#### Scenario: Identifier returned and documented

- **WHEN** a generation succeeds
- **THEN** the response carries an identifier
- **AND** the published contract states it is not retrievable

### Requirement: Devices are discoverable over HTTP

The API SHALL expose the available devices and, for one device, enough detail
for a client to present it and pre-fill its options: its plan heading levels
and its anchor marker spelling. Filenames and function names are decided per
case inside the device's module, so they are not published here.

#### Scenario: Device detail

- **WHEN** a client requests a known device
- **THEN** the response carries its heading levels and its anchor markers

#### Scenario: Unknown device

- **WHEN** a client requests a device that does not exist
- **THEN** the response is 404
- **AND** the error details name the devices that do exist

### Requirement: Parsing is available without a device

The API SHALL offer a dry run that returns the parsed cases and steps together
with diagnostics, without generating code and without requiring a device, so a
client can preview a plan as it is typed and validate its format before a target
is chosen. A device MAY be supplied solely to adopt its heading conventions.

#### Scenario: Preview without a device

- **WHEN** a plan is submitted for parsing with no device
- **THEN** the response carries its cases, their steps and any diagnostics

#### Scenario: Recoverable problems still succeed

- **WHEN** a submitted plan misnumbers a step
- **THEN** the response is 200 and carries the corresponding diagnostic

### Requirement: Regeneration in place without server state

A generation request SHALL accept the current content of the files it is to
produce. For each such file the anchored regions SHALL be rewritten and the rest
preserved, and the artifact SHALL be reported as updated rather than created.

#### Scenario: Round trip reports updated

- **WHEN** a client submits the artifacts of a previous generation as the
  existing files of a new one, with an unchanged plan
- **THEN** every artifact is reported as updated
- **AND** the content is identical to the previous generation

#### Scenario: Supplied file lacks the anchors

- **WHEN** a submitted existing file does not contain the device's markers
- **THEN** the response is 422 with a missing-anchor error naming the anchor

### Requirement: Status codes distinguish fault and cause

The API SHALL assign status codes by who must act and why: 400 for a body that
does not match the schema, 404 for an unknown device, 413 for input over the
size limit, 422 for input whose content cannot be used, and 5xx for a
defective device or template.

#### Scenario: Schema violation is a client error, not unprocessable content

- **WHEN** a request body carries an unrecognised field
- **THEN** the response is 400, reserving 422 for usable-shape but unusable content

#### Scenario: Unusable plan

- **WHEN** a submitted plan yields no usable case
- **THEN** the response is 422 and carries the diagnostics explaining why

#### Scenario: Oversized input

- **WHEN** a submitted plan exceeds the published size limit
- **THEN** the response is 413

### Requirement: One error envelope for every failure

Every 4xx and 5xx response SHALL use a single envelope carrying a stable error
code, a human-readable message, structured details, and the diagnostics
collection. Server-fault responses SHALL omit internal details from the body.

#### Scenario: Consistent shape

- **WHEN** any request fails
- **THEN** the body carries an error code, a message, a details object and a
  diagnostics collection

#### Scenario: Server fault withholds internals

- **WHEN** a failure is attributable to a defective device or template
- **THEN** the response body carries no internal paths or stack detail

### Requirement: Submitted content is not echoed in validation errors

A validation failure SHALL NOT include the rejected input values, so that an
error response cannot become larger than the request that caused it or restate
the submitted plan.

#### Scenario: Rejected body is not returned

- **WHEN** a request with an invalid field also carries a large plan
- **THEN** the error response does not contain the plan's text

### Requirement: Strict request validation

Request bodies SHALL reject unrecognised fields rather than ignore them, so a
misspelled option is reported instead of silently falling back to a default.

#### Scenario: Misspelled option

- **WHEN** a request carries a misspelling of a documented option field
- **THEN** the request is rejected rather than generated with the default

### Requirement: Options default to the device, not the schema

A generation option the caller omits SHALL fall back to the device's own value
rather than to a schema default, so omitting an option is always safe.

#### Scenario: Partial override

- **WHEN** a request overrides only the step heading level
- **THEN** every other option takes the device manifest's value

### Requirement: Browser-friendly download representations

The generation endpoint SHALL offer its result as an archive and, for a
single-file result, as that file's raw content, selected by a request parameter
rather than by content negotiation so that an ordinary HTML form post can
trigger a download without client-side scripting. Requesting the single-file
representation for a multi-file result SHALL be rejected with guidance.

#### Scenario: Archive download

- **WHEN** a generation requests the archive representation
- **THEN** the response is an archive with a filename disposition containing
  every artifact

#### Scenario: Single-file representation with several artifacts

- **WHEN** a generation producing several files requests the single-file
  representation
- **THEN** the response is 400
- **AND** the message states how to narrow the request or obtain an archive

### Requirement: The API documents itself

The API SHALL publish a machine-readable description covering every route, with
usable request examples, so it serves as the manual test surface before any user
interface exists and as the source for generated clients.

#### Scenario: Every route is described

- **WHEN** the published description is retrieved
- **THEN** it documents every available route with its request and response shapes
