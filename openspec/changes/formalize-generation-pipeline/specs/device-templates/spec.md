# Spec Delta

## Purpose

Defines the contract between TestForge and a generation target. A device
declares, as data, how its test plans are written and what files come out, so a
team can add or change a target without changing TestForge's code.

## ADDED Requirements

### Requirement: A device is declarative

Adding or modifying a device SHALL require only data and template files, never
changes to application code. A device SHALL consist of a manifest plus the
templates it references.

#### Scenario: New device added without code changes

- **WHEN** a directory containing a valid manifest and its templates is placed
  on a device search path
- **THEN** that device becomes available for generation with no code change and
  no redeployment of application logic

### Requirement: Manifest declares the full generation contract

A manifest SHALL declare the device's identity, its plan heading conventions, its
step naming pattern, its anchor marker spelling, and its output files. Each
output SHALL declare its filename pattern, its skeleton template, and which
fragment template fills which anchor.

#### Scenario: Multi-file output

- **WHEN** a manifest declares a header output carrying one anchor and a source
  output carrying two
- **THEN** generating one case produces both files
- **AND** each file reports exactly the anchors it carries

#### Scenario: Filename derived from the case

- **WHEN** an output declares the filename pattern `test_{case_snake}.cpp`
- **THEN** a case titled `Sensor Fault Recovery` produces `test_sensor_fault_recovery.cpp`

### Requirement: Template context is a stable contract

The set of values available to templates SHALL be a documented contract covering
the device, the case, its steps with their resolved function names, the file
being produced, and every file produced for that case. Templates SHALL be able
to reference sibling outputs so a source file can include its own header.

#### Scenario: Source file includes its generated header

- **WHEN** a source template references the sibling output whose extension is `.h`
- **THEN** the generated source includes that header by its generated filename

#### Scenario: Step function names are supplied, not derived in templates

- **WHEN** a fragment template renders a step
- **THEN** the step's resolved C++ function name is available directly, so the
  template performs no identifier construction of its own

### Requirement: Manifests are validated when loaded

A device SHALL be validated at load time and a defect SHALL prevent startup
rather than surface on a user's first request. Validation SHALL cover schema
conformance, unknown keys, identity matching the directory name, referenced
template files existing, placeholder validity in naming and filename patterns,
and anchor markers carrying a name placeholder.

#### Scenario: Referenced template is missing

- **WHEN** a manifest names a template file that does not exist
- **THEN** loading fails and the error names the missing file

#### Scenario: Identity does not match its directory

- **WHEN** a manifest's identifier differs from its directory name
- **THEN** loading fails, so devices stay findable by name

#### Scenario: Unknown manifest key

- **WHEN** a manifest contains a misspelled top-level key
- **THEN** loading fails rather than silently ignoring it

#### Scenario: Step placeholder used in a filename

- **WHEN** an output filename pattern references a step-level placeholder, for
  which no step is in scope at file level
- **THEN** loading fails and the error names that placeholder

### Requirement: Devices are discovered from several roots

Devices SHALL be discovered from the packaged set, from a conventional directory
in the working project, and from an environment-configured search path. A device
found in a later root SHALL shadow an earlier one with the same identifier, so a
project can override a packaged device without editing it.

#### Scenario: Project device shadows a packaged one

- **WHEN** a project directory contains a device whose identifier matches a
  packaged device
- **THEN** generation uses the project's device

### Requirement: A reference device is provided

The system SHALL ship a documented reference device demonstrating multi-file
output, multiple anchors and the template context, usable as the starting point
for a real device.

#### Scenario: Reference device generates compilable code

- **WHEN** a plan is generated with the reference device and compiled together
  with the reference runtime it provides
- **THEN** the code compiles without warnings under a strict warning
  configuration
- **AND** running it reports failures for steps that are still unimplemented,
  rather than passing silently
