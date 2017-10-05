# TODO: Add todo task.
# TODO: Switch to pyenv

HERE = $(shell pwd)
VENV = $(HERE)/venv
BIN = $(VENV)/bin
PYTHON = $(BIN)/python

INSTALL = $(BIN)/pip install --no-deps
VTENV_OPTS ?= --distribute

# Tasks
# -----

.PHONY: help
help: ## Show this message.

	@echo "usage: make [task]" \
	&& echo "available tasks:" \
	&& awk \
		'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / \
		{printf "$(CYAN)%-8s$(WHITE) : %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: all test docs build_extras

all: build

$(PYTHON):
	virtualenv $(VTENV_OPTS) $(VENV)

build: $(PYTHON)
	$(PYTHON) setup.py develop

clean:
	rm -rf $(VENV)

test_dependencies:
	$(BIN)/pip install flake8 tox unittest2

test: build test_dependencies
	$(BIN)/flake8 boom
	$(BIN)/tox
