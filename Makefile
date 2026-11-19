.PHONY: test lint check run json install uninstall

UV ?= uv
EXT_DIR := extension/agents-providers-bar@ailton.local

test:
	$(UV) run python -m unittest discover -s backend/tests -v

lint:
	node --check $(EXT_DIR)/extension.js
	$(UV) run python -m json.tool $(EXT_DIR)/metadata.json >/dev/null

check: lint test

run:
	$(UV) run agents-usage --no-cache

json:
	$(UV) run agents-usage --json --no-cache

install:
	./scripts/install.sh

uninstall:
	./scripts/uninstall.sh
