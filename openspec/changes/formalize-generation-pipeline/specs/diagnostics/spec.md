# Spec Delta

## Purpose

Defines how TestForge reports problems that do not prevent it from producing
output. Test plans are written by hand and are reliably inconsistent, so the
system reports what it found and carries on instead of failing on the first
irregularity.

## ADDED Requirements

### Requirement: Recoverable problems are returned, not raised

A problem that does not prevent output SHALL be returned alongside the result
rather than raised as a failure, so that a single run reports every issue in the
input instead of one per attempt.

#### Scenario: Several independent problems in one plan

- **WHEN** a plan contains a step with no description and another step whose
  written number disagrees with its position
- **THEN** generation succeeds
- **AND** both problems are reported in the same result

### Requirement: Severity determines whether output is produced

Each diagnostic SHALL carry one of three severities with defined consequences:
error means no output can be produced, warning means output was produced but may
not be what the author intended, and info is advisory only.

#### Scenario: Warning does not block output

- **WHEN** the only diagnostics are warnings and advisories
- **THEN** artifacts are produced

#### Scenario: Error blocks output

- **WHEN** any diagnostic is error-severity
- **THEN** no artifacts are produced and the diagnostics are reported

### Requirement: Diagnostic codes are stable identifiers

Each diagnostic SHALL carry a stable machine-readable code distinct from its
human-readable message. Clients and tests SHALL rely on the code; the message
text SHALL be free to be reworded.

#### Scenario: Client branches on the code

- **WHEN** a plan misnumbers a step
- **THEN** the diagnostic's code is `step.index_mismatch` regardless of how the
  message is phrased

### Requirement: Diagnostics locate the problem

A diagnostic SHALL carry the location of the problem where one applies: the
1-based line in the submitted source, and the case and step it concerns.

#### Scenario: Step problem reports its line

- **WHEN** a diagnostic concerns a specific step
- **THEN** it carries the line of that step's heading and the step's position

### Requirement: Diagnostics accumulate across stages

Diagnostics produced while parsing, naming and assembling one request SHALL be
reported together, so a caller never has to fix a parse problem before learning
about a naming problem.

#### Scenario: Parse and request problems reported together

- **WHEN** a request selects a case that does not exist in a plan that also has
  advisory parse diagnostics
- **THEN** the failure reports both the out-of-range selection and the parse
  diagnostics

### Requirement: Failures carrying diagnostics use the same shape

A failure caused by the content of the input SHALL report its diagnostics in the
same structure as a successful result, so one rendering path handles both.

#### Scenario: Unusable plan

- **WHEN** a plan yields no usable case
- **THEN** the failure response carries a diagnostics collection of the same
  shape as a successful response
