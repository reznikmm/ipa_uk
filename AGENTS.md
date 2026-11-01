# AGENTS.md

## Purpose

Munin is an Ada library for ....

## Repository Map

- `source/`: Core library logic (`Ipa_Uk.*` packages)
- `testsuite/`: Separate test suite crate
- `config/`: Build-time configuration artifacts written by Alire (do not edit manually)
- `.obj/`, `.lib/`: Build outputs (do not edit manually)

## Ground Rules

- Don't suppress exception with `null;` exception handler
   (one exception is `Libadalang.Common.Property_Error`).
- Don't introduce extra (sub-)type conversions, like Integer to Natural.
- Preserve existing style and naming conventions in nearby code. Don't use abbreviations.

## Build And Test Commands

Run from repository root unless noted otherwise.

- Compile core library:
  - `alr build`
- Compile/check one file (`<unit>.adb`):
  - `alr exec -- gprbuild -q -f -c -u -gnatc -P ipa_uk.gpr <unit>.adb '-cargs:ada' -gnatef`
- Fix code style warnings, force code style after edit:
  - `alr exec -- gnatformat --charset=utf-8 --no-subprojects -P ipa_uk.gpr`
- Build and run testsuite:
  - `alr -C testsuite/ run`

## Change Workflow For Agents

1. Read relevant package spec/body before editing. Read `*.adb` only if reading of corresponding `*.ads` is not enough.
2. Implement the smallest viable patch.
3. Re-run compile check for touched units.
4. Run targeted runtime/test command when behavior changes.
5. Report exactly what changed and what was validated.

## Ada-Specific Notes

- Use predefined Ada container packages
  (for example, `Ada.Containers.Hashed_Sets`). Don't use Indefinite containers.
- Use Ada 2022 syntax if you can.

## Output And Error Handling Expectations

- Diagnostics should be actionable and include path/context when possible.

## When Unsure

- Prefer conservative changes.
- Ask for clarification before large architectural rewrites.
- Document assumptions in the final update.
