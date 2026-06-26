# Makefile for Workana-Bot Admin Commands

PROJECT_ROOT := .

.PHONY: help create-user update-password delete-projects delete-all prune-projects tests

help:
	@echo "Available commands:"
	@echo "  make create-user              Create a new user via CLI (hidden password)"
	@echo "  make update-password          Update user password via CLI"
	@echo "  make delete-projects DATE=... Delete projects from a given date (YYYY-MM-DD)"
	@echo "  make delete-all               Delete ALL projects"
	@echo "  make prune-projects           Physically delete all soft-deleted projects"
	@echo "  make tests                    Run all unit tests"

create-user:
	PYTHONPATH=. python scripts/command.py create-user

update-password:
	PYTHONPATH=. python scripts/command.py update-password

delete-projects:
	PYTHONPATH=. python scripts/command.py delete-projects --from-date $(DATE)

delete-all:
	PYTHONPATH=. python scripts/command.py delete-projects --all

prune-projects:
	PYTHONPATH=. python scripts/command.py prune-projects

tests:
	PYTHONPATH=. python -m pytest tests/unit/ -v