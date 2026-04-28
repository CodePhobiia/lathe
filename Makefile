# Thin wrapper around the Justfile. `just` is the canonical task runner
# (https://just.systems/). This Makefile requires `just`; every recipe lives
# in the Justfile.
#
# Install `just` from https://just.systems/ and
# invoke `just <target>` directly — every recipe lives in the Justfile.

.PHONY: bootstrap deps-check doctor test lint lint-required lint-format-advisory mypy-advisory build-heroes docs security-local release-local ci ci-fast-test ci-contract-golden ci-property ci-coverage ci-examples-check ci-corpus-pytest clean-clone-readme devcontainer-validate help

help:
	@just --list

bootstrap:
	just bootstrap

deps-check:
	just deps-check

doctor:
	just doctor

test:
	just test

lint:
	just lint

lint-required:
	just lint-required

lint-format-advisory:
	just lint-format-advisory

mypy-advisory:
	just mypy-advisory

build-heroes:
	just build-heroes

docs:
	just docs

security-local:
	just security-local

release-local:
	just release-local

ci:
	just ci

ci-fast-test:
	just ci-fast-test

ci-contract-golden:
	just ci-contract-golden

ci-property:
	just ci-property

ci-coverage:
	just ci-coverage

ci-examples-check:
	just ci-examples-check

ci-corpus-pytest:
	just ci-corpus-pytest

clean-clone-readme:
	just clean-clone-readme

devcontainer-validate:
	just devcontainer-validate
