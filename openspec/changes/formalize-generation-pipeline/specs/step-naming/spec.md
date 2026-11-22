# Spec Delta

## Purpose

Defines how a human-written step title becomes an identifier in generated
code, and the helpers a device uses to do it. Generated names appear in
committed code and in test reports, so they must be legal and stable enough
that editing a plan's prose does not churn the diff.

## ADDED Requirements

### Requirement: The naming rule belongs to the device

Each device SHALL decide its own step function names. The framework SHALL call
the device's rule once per step and make the result available wherever that
step is rendered, so a module never derives the same name twice.

#### Scenario: Device controls the name

- **WHEN** a device's rule produces a name for a step
- **THEN** that exact name appears in the generated declaration, call and
  definition for that step

#### Scenario: Rule is called with the step's own data

- **WHEN** the rule is invoked
- **THEN** it receives the step's position, title, declared number, body,
  expectation and source line

### Requirement: Helpers produce legal identifiers

The framework SHALL provide the conversions a device needs — identifier
casing, string-literal escaping, comment rendering and include-guard
derivation — so each device does not re-implement them. The identifier helper
SHALL produce a legal, non-reserved identifier.

#### Scenario: Reserved word

- **WHEN** a name would be a reserved word
- **THEN** the helper returns an escaped form instead

#### Scenario: Leading digit

- **WHEN** a name would begin with a digit
- **THEN** the helper returns a form that is legal to declare

#### Scenario: Acronyms survive casing

- **WHEN** a title contains an all-capital word
- **THEN** the casing helper keeps it capitalised rather than title-casing it

#### Scenario: Accents fold to ASCII

- **WHEN** a title contains accented Latin characters
- **THEN** the casing helper yields their unaccented ASCII equivalents

### Requirement: Index-prefixed naming is the recommended default

The example devices SHALL name steps with their position before the title, so
a name survives a retitle, keeps the plan's order in the generated file, and
is unique without a deduplication suffix.

#### Scenario: Default naming in the examples

- **WHEN** an example device generates a case whose first step is titled
  "Power on the board"
- **THEN** the generated function name contains both the position 1 and the
  title, in that order

### Requirement: A rule that produces nothing usable is an error

Generation SHALL fail, naming the device and the step, when a device's naming
rule returns an empty value. The system SHALL NOT substitute a name of its own
and carry on.

#### Scenario: Empty name

- **WHEN** a device's rule returns an empty string for a step
- **THEN** generation fails with an error identifying that step
