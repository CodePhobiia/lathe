# Thin wrapper around the Justfile. `just` is the canonical task runner
# (https://just.systems/). This Makefile exists so users without `just`
# installed still have a familiar entry point.
#
# If you do not have `just`, install it from https://just.systems/ and
# invoke `just <target>` directly — every recipe lives in the Justfile.

.PHONY: bootstrap doctor test lint build-heroes docs ci help

help:
	@just --list

bootstrap:
	just bootstrap

doctor:
	just doctor

test:
	just test

lint:
	just lint

build-heroes:
	just build-heroes

docs:
	just docs

ci:
	just ci
