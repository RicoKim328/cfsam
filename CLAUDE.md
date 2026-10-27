# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

This repository (`cfsam`, MIT-licensed) is newly initialized and contains no source code, build files, or tests yet — only `LICENSE`. Update this file once code, build commands, and architecture exist.

## Context: surrounding cFS bundle

The checkout lives inside a NASA Core Flight System (cFS) bundle at `../` (`~/Desktop/Project/cFS`), which is a separate git repository where `cfsam/` is untracked. Nothing in the bundle's build (`targets.cmake`, Makefiles) references `cfsam` yet.

Bundle build/test commands are run from the bundle root, not from this repo:

```bash
make native_std.prep           # set up build tree (other configs, e.g. native_eds, work the same way)
make native_std.install        # compile and stage to build-native_std/exe
make native_std.runtest        # run unit tests
make native_std.lcov           # coverage (requires runtest to pass)
cd build-native_std/exe/cpu1 && ./core-cpu1   # run cFS
```

Per the bundle README, a new cFS app is typically started from `sample_app`/`skeleton_app`, then must be added to the target's `targets.cmake` to be compiled and to the `cfe_es_startup.scr` file to be loaded at runtime.
