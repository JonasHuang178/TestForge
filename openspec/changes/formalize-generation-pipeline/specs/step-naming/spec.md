# Spec Delta

## Purpose

Defines how a human-written step title becomes a C++ identifier. Generated names
appear in committed code and in test reports, so they must be legal, unique and
stable enough that editing a plan's prose does not churn the generated diff.

## ADDED Requirements

### Requirement: Index-prefixed naming by default

The default step function name SHALL include the step's position before its
title, so that a name survives retitling, preserves plan order in the generated
file, and is unique without needing a deduplication suffix.

#### Scenario: Default pattern applied

- **WHEN** a case's first two steps are titled `Power on the device` and
  `Read firmware version`
- **THEN** the generated names are `TestStep_01_PowerOnTheDevice` and
  `TestStep_02_ReadFirmwareVersion`

### Requirement: Naming pattern is configurable

A device SHALL declare its step naming pattern, and a request SHALL be able to
override it. The pattern exposes step-level and case-level placeholders.

#### Scenario: Request overrides the device pattern

- **WHEN** a generation requests the pattern `{case_pascal}_{snake_title}`
- **THEN** names follow that pattern instead of the device's default

### Requirement: Unknown placeholders are rejected

A naming pattern referencing a placeholder the system does not provide SHALL be
rejected with an error identifying the offending placeholder and listing the
valid ones. A device manifest's pattern SHALL be validated when the device is
loaded, not when it is first used.

#### Scenario: Typo in a request pattern

- **WHEN** a generation requests the pattern `Step_{bogus}`
- **THEN** the request is rejected as invalid
- **AND** the error names `bogus` and lists the available placeholders

#### Scenario: Typo in a device manifest

- **WHEN** a manifest declares a pattern with an unknown placeholder
- **THEN** loading that device fails

### Requirement: Generated names are legal C++ identifiers

Every generated name SHALL be a legal identifier that does not collide with a
reserved word. Characters illegal in an identifier SHALL be removed, a leading
digit SHALL be made legal, and a reserved word SHALL be escaped.

#### Scenario: Reserved word

- **WHEN** a pattern would produce the identifier `class`
- **THEN** the emitted identifier is `class_`

#### Scenario: Leading digit

- **WHEN** a pattern would produce the identifier `2nd`
- **THEN** the emitted identifier is `_2nd`

### Requirement: Non-ASCII titles

Accented Latin characters SHALL be folded to their ASCII equivalents. A title
with no usable ASCII characters SHALL fall back to a positional name and report a
diagnostic, so that the file still compiles and the author learns why the name is
unhelpful.

#### Scenario: Accents are folded

- **WHEN** a step is titled `Prüfung läuft`
- **THEN** the title contributes `PrufungLauft` to the identifier

#### Scenario: Title with no ASCII equivalent

- **WHEN** a step at position 1 is titled `初始化裝置`
- **THEN** the identifier falls back to the positional form `TestStep_01_Step1`
- **AND** a `naming.title_not_representable` warning is reported

### Requirement: Names are unique within a case

Two steps of the same case SHALL NOT produce the same identifier. A collision
SHALL be resolved with a numeric suffix and reported, so the author can decide
whether the duplicate titles were intentional. Identical titles in different
cases SHALL be free to repeat.

#### Scenario: Duplicate titles collide under a title-only pattern

- **WHEN** a case has two steps titled `Reset` and the pattern omits the index
- **THEN** the identifiers are `Step_Reset` and `Step_Reset_2`
- **AND** a `naming.duplicate` warning is reported for the second

#### Scenario: Same title in a different case

- **WHEN** two different cases each contain a step titled `Reset`
- **THEN** both may produce the same identifier without a diagnostic
