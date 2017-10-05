# TODO: Switch to pyenv

HERE = $(shell pwd)
VENV = $(HERE)/venv
BIN = $(VENV)/bin
PYTHON = $(BIN)/python

INSTALL = $(BIN)/pip install --no-deps
VTENV_OPTS ?= --distribute

# List of code tags to search for.
TODO_TAGS = TODO|FIXME|CHANGED|XXX|REVIEW|BUG|REFACTOR|IDEA|WARNING

# Colors.
WHITE  = \033[0m
RED    = \033[31m
GREEN  = \033[32m
YELLOW = \033[33m
BLUE   = \033[34m
CYAN   = \033[36m

# Tasks
# -----

.PHONY: help
help: ## Show this message.

	@echo "usage: make [task]" \
	&& echo "available tasks:" \
	&& awk \
		'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / \
		{printf "$(CYAN)%-8s$(WHITE) : %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: todo
todo: ## Show todo list.

	@find . \
		-type f \
		-not -path "./.git/*" \
		-exec \
			awk '/[ ]($(TODO_TAGS)):/ \
				{ \
					gsub("# ","", $$0); \
					gsub("// ","", $$0); \
					gsub(/^[ \t]+/, "", $$0); \
					gsub(/:/, "", $$0); \
					gsub(/\.\//,"", FILENAME); \
					TYPE = $$1; $$1 = ""; \
					MESSAGE = $$0; \
					LINE = NR; \
					printf \
					"$(CYAN)%s|$(WHITE):%s|: $(CYAN)%s$(WHITE)($(BLUE)%s$(WHITE))\n"\
					, TYPE, MESSAGE, FILENAME, LINE \
				}' \
		{} \; | column -s '|' -t

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
