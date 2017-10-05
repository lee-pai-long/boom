# TODO: Add pylint and/or codeclimate.

# Switch to bash instead of sh
SHELL := /bin/bash

# Project constants
# -----------------
APP_NAME := boom

# List of code tags to search for.
TODO_TAGS := TODO|FIXME|CHANGED|XXX|REVIEW|BUG|REFACTOR|IDEA|WARNING

# Colors.
WHITE  = \033[0m
RED    = \033[31m
GREEN  = \033[32m
YELLOW = \033[33m
BLUE   = \033[34m
CYAN   = \033[36m

# Python shortcuts.
PYENV_ROOT 			?= $$HOME/.pyenv
PYENV_INSTALLER		:= https://goo.gl/YnAzjE
PYTHON_VERSION		:= $$(cat .python-version)
REQUIREMENTS	 	:= requirements-test.txt
BASH_RC 			?= $$HOME/.bash_profile
PIP					 = $(PYENV_ROOT)/versions/$(APP_NAME)/bin/pip

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
		-not -path "./*.egg-info/*" \
		-not -path "./.tox/*" \
		-exec \
			awk '/[ ]($(TODO_TAGS)):/ \
				{ \
					gsub("# ","", $$0); \
					gsub("// ","", $$0); \
					gsub(/\.\./,"", $$0); \
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

.PHONY: pyenv
pyenv: ## Install pyenv(python version manager).

	@which pyenv &> /dev/null \
	|| (curl -L https://goo.gl/YnAzjE | PYENV_ROOT=$(PYENV_ROOT) bash \
		&& echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> $(BASH_RC) \
		&& echo 'eval "$(pyenv init -)"' >> $(BASH_RC) \
		&& echo 'eval "$(pyenv virtualenv-init -)"' >> $(BASH_RC) \
		&& source $(BASH_RC))

.PHONY: python
python: pyenv ## Install python version define in .python-version.

	@pyenv install -s

.PHONY: venv
venv: python ## Create a local virtualenv for the project.

	@pyenv virtualenvs | grep $(APP_NAME) \
	|| (pyenv virtualenv $(PYTHON_VERSION) $(APP_NAME) \
		&& $(PIP) install \
				--requirement $(REQUIREMENTS) \
				--upgrade )

.PHONY: dev
dev: venv ## Install boom locally (inside the virtualenv).

	@$(PIP) install --no-deps --editable .
