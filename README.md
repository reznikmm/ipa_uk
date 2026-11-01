Ipa_Uk
========

[![Build with Alire](https://github.com/reznikmm/ipa_uk/actions/workflows/alire.yml/badge.svg)](https://github.com/reznikmm/ipa_uk/actions/workflows/alire.yml)
[![REUSE status](https://api.reuse.software/badge/github.com/reznikmm/ipa_uk)](https://api.reuse.software/info/github.com/reznikmm/ipa_uk)

Ada crate to generate IPA (international phonetic alphabet) for ukrainian words

## What Is Included

This repository is a minimal starting point for IPA for ukrainian words in Ada 2022 with:

- a library crate in the repository root
- a separate example usage procedure in `examples/`
- CI workflows for build/test (`alire.yml`) and REUSE compliance (`reuse.yml`)
- SPDX and [REUSE](https://reuse.software/) metadata (`REUSE.toml`, `LICENSES/`)
- Python scripts to (re-)generate tables from Python [reference implementatin](https://github.com/lang-uk/ipa-uk)

Key directories and files:

- `source/` - library units (`Ipa_Uk` package)
- `ipa_uk.gpr` - root GPR project file for the library
- `alire.toml` - root crate metadata and test action
- `examples/` - separate example
- `AGENTS.md` - repository-specific instructions for coding agents

## Requirements

- [Alire](https://alire.ada.dev/)
- GNAT toolchain compatible with Ada 2022

## Build

From repository root:

```sh
alr build
```

## Using This Ipa_Uk

TBD

## Maintainer

[Max Reznik](https://github.com/reznikmm)

## License

Licensed under Apache-2.0 WITH LLVM-exception. See `LICENSES/` and `REUSE.toml`.

