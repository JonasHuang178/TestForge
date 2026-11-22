# Spec Delta

## Purpose

Defines the contract between TestForge and a generation target. A device
supplies the rules that differ between targets — naming, filenames, emitted
code — while the framework keeps the guarantees that must hold for all of
them, so adding a target never means re-implementing safe code injection.

## ADDED Requirements

### Requirement: A device is a folder holding a module and its templates

A device SHALL consist of one Python module plus the source files it fills in.
Adding or changing a device SHALL require no change to application code, and a
device's identity SHALL match its folder name so devices stay findable.

#### Scenario: New device added without touching the application

- **WHEN** a folder containing a device module and its templates is placed on
  a device search path
- **THEN** that device becomes available for generation with no code change

#### Scenario: Identity does not match its folder

- **WHEN** a module declares an identity different from its folder name
- **THEN** loading that device fails

### Requirement: The module owns naming, filenames and emitted code

A device module SHALL decide what a step's function is called, which files a
case produces, and what code goes into each anchored region. These SHALL be
expressed as code, not configuration, because the rules differ between targets
in ways a fixed schema cannot describe.

#### Scenario: One case, one self-contained file

- **WHEN** a device's module returns a single output for a case
- **THEN** generation produces exactly that file

#### Scenario: One case, a header and a source file

- **WHEN** a device's module returns a header and a source output
- **THEN** both are produced, each carrying only the anchors it declares

#### Scenario: The naming rule is the module's

- **WHEN** two devices name the same step differently
- **THEN** each device's generated code uses its own name, with no shared
  pattern language in between

### Requirement: A module declares a minimum contract, checked at load

A device module SHALL declare its identity, its display name, how a step
becomes a function name, and how a case becomes output files. The contract
SHALL be checked when the registry loads, so a defective device stops startup
rather than failing a user's first request.

#### Scenario: Required definition missing

- **WHEN** a module omits one of the required definitions
- **THEN** loading fails and the error names what is missing

#### Scenario: Module raises while being imported

- **WHEN** importing a device module raises
- **THEN** loading fails and the error names the exception

#### Scenario: Naming rule returns nothing usable

- **WHEN** a module's naming rule returns an empty value for a step
- **THEN** generation fails with an error naming the device and the step,
  rather than emitting a file with a nameless function

#### Scenario: Module returns the wrong kind of thing

- **WHEN** a module's build step returns something other than output
  descriptions
- **THEN** generation fails with an error naming the device

### Requirement: Templates are plain source files with placeholders

A template SHALL be an ordinary source file in the device's folder, carrying
the device's anchor markers. Placeholder substitution SHALL use a syntax that
cannot occur in C or C++ by accident, and SHALL apply only when an output file
is first created.

#### Scenario: Placeholders filled on creation

- **WHEN** a case is generated into a file that does not exist yet
- **THEN** the template's placeholders are replaced with the module's values
- **AND** no placeholder remains in the output

#### Scenario: Placeholder with no value supplied

- **WHEN** a template uses a placeholder the module supplies no value for
- **THEN** generation fails and the error names the placeholder

#### Scenario: Placeholders are not reapplied on regeneration

- **WHEN** an existing file is regenerated
- **THEN** only its anchored regions change; text that came from a placeholder
  is left as the file has it

#### Scenario: Template file missing

- **WHEN** a module names a template that is not in its folder
- **THEN** generation fails and the error names the device and the template

### Requirement: A device may choose its anchor marker spelling

A device SHALL be able to declare how its begin and end markers are written,
so a target whose language has no line comments can still be generated. The
default SHALL be a line-comment form.

#### Scenario: Block-comment markers

- **WHEN** a device declares block-comment markers
- **THEN** its templates are matched on those markers and generation succeeds

### Requirement: Devices are discovered from several roots

Devices SHALL be discovered from a conventional directory in the working
project and from an environment-configured search path. A device found in a
later root SHALL shadow an earlier one with the same identity. A folder with
no device module SHALL be skipped without error, so a devices directory may
also hold shared headers.

#### Scenario: Shared directory overrides a project device

- **WHEN** a device on the configured search path has the same identity as one
  in the project directory
- **THEN** generation uses the one from the search path

#### Scenario: Folder that is not a device

- **WHEN** a devices directory contains a folder with no device module
- **THEN** it is ignored and the other devices still load

### Requirement: Worked examples are provided

The project SHALL ship at least one minimal device producing a single
self-contained file, and one producing a header and source pair, usable as the
starting point for a real device.

#### Scenario: Example output compiles

- **WHEN** a plan is generated with an example device and compiled
- **THEN** the code compiles without warnings under a strict warning
  configuration
- **AND** running it reports failures for steps that are still unimplemented,
  rather than passing silently
