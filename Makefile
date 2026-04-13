SHELL := /bin/bash
DB_HOST ?= 127.0.0.1
DB_PORT ?= 5432
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
FE_HOST ?= 0.0.0.0
FE_PORT ?= 5173
UPDATE_DATE ?= 2026-03-30
PYTHON_BIN ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PIP_BIN ?= $(if $(wildcard .venv/bin/pip),.venv/bin/pip,pip3)
STREAMLIT_BIN ?= $(if $(wildcard .venv/bin/streamlit),.venv/bin/streamlit,streamlit)

.PHONY: help install install-be install-fe env db db-down wait-db db-status api api-stop fe fe-stop dashboard dev build-fe updatedb

help:
	@echo "Available targets:"
	@echo "  make install      - install backend and frontend dependencies"
	@echo "  make env          - create backend/.env from backend/.env.example if missing"
	@echo "  make db           - start PostgreSQL with Docker Compose"
	@echo "  make wait-db      - wait until PostgreSQL accepts TCP connections"
	@echo "  make db-status    - show PostgreSQL container status"
	@echo "  make db-down      - stop PostgreSQL"
	@echo "  make api          - run FastAPI backend"
	@echo "  make api-stop     - stop any process using API_PORT"
	@echo "  make fe           - run Vite frontend"
	@echo "  make fe-stop      - stop any process using FE_PORT"
	@echo "  make dashboard    - run Streamlit dashboard"
	@echo "  make dev          - start DB, API, and FE together"
	@echo "  make build-fe     - production build for frontend"
	@echo "  make updatedb     - sync DB for one date, default UPDATE_DATE=$(UPDATE_DATE)"

install: install-be install-fe

install-be:
	$(PIP_BIN) install -r backend/requirements.txt

install-fe:
	cd frontend && npm install

env:
	@if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; fi

db:
	cd backend && docker compose up -d

wait-db:
	@echo "Waiting for PostgreSQL on $(DB_HOST):$(DB_PORT)..."
	@for i in {1..60}; do \
		(echo > /dev/tcp/$(DB_HOST)/$(DB_PORT)) >/dev/null 2>&1 && exit 0; \
		sleep 1; \
	done; \
	echo "PostgreSQL is not ready on $(DB_HOST):$(DB_PORT)"; \
	exit 1

db-status:
	cd backend && docker compose ps

db-down:
	cd backend && docker compose down

api:
	PYTHONPATH=backend/src $(PYTHON_BIN) -m uvicorn silver_timeseri.api:app --host $(API_HOST) --port $(API_PORT) --reload

api-stop:
	@pids=$$(lsof -ti tcp:$(API_PORT) 2>/dev/null || true); \
	if [ -n "$$pids" ]; then \
		echo "Stopping API process on port $(API_PORT): $$pids"; \
		kill $$pids 2>/dev/null || true; \
		for i in {1..10}; do \
			sleep 1; \
			remaining=$$(lsof -ti tcp:$(API_PORT) 2>/dev/null || true); \
			[ -z "$$remaining" ] && exit 0; \
		done; \
		remaining=$$(lsof -ti tcp:$(API_PORT) 2>/dev/null || true); \
		if [ -n "$$remaining" ]; then \
			echo "Force stopping API process on port $(API_PORT): $$remaining"; \
			kill -9 $$remaining 2>/dev/null || true; \
		fi; \
	else \
		echo "No process is using API port $(API_PORT)"; \
	fi

fe:
	cd frontend && npm run dev -- --host $(FE_HOST) --port $(FE_PORT)

fe-stop:
	@pids=$$(lsof -ti tcp:$(FE_PORT) 2>/dev/null || true); \
	if [ -n "$$pids" ]; then \
		echo "Stopping frontend process on port $(FE_PORT): $$pids"; \
		kill $$pids 2>/dev/null || true; \
		for i in {1..10}; do \
			sleep 1; \
			remaining=$$(lsof -ti tcp:$(FE_PORT) 2>/dev/null || true); \
			[ -z "$$remaining" ] && exit 0; \
		done; \
		remaining=$$(lsof -ti tcp:$(FE_PORT) 2>/dev/null || true); \
		if [ -n "$$remaining" ]; then \
			echo "Force stopping frontend process on port $(FE_PORT): $$remaining"; \
			kill -9 $$remaining 2>/dev/null || true; \
		fi; \
	else \
		echo "No process is using FE port $(FE_PORT)"; \
	fi

dashboard:
	$(STREAMLIT_BIN) run backend/dashboard.py

build-fe:
	cd frontend && npm run build

updatedb:
	PYTHONPATH=backend/src $(PYTHON_BIN) -m silver_timeseri.cli sync-db --start-date $(UPDATE_DATE) --end-date $(UPDATE_DATE) --timeframe 1d

dev:
	@api_pids=$$(lsof -ti tcp:$(API_PORT) 2>/dev/null || true); \
	if [ -n "$$api_pids" ]; then \
		echo "API port $(API_PORT) is already in use by: $$api_pids"; \
		echo "Run 'make api-stop' or use a different port: make dev API_PORT=8001"; \
		exit 1; \
	fi; \
	fe_pids=$$(lsof -ti tcp:$(FE_PORT) 2>/dev/null || true); \
	if [ -n "$$fe_pids" ]; then \
		echo "Frontend port $(FE_PORT) is already in use by: $$fe_pids"; \
		echo "Run 'make fe-stop' or use a different port: make dev FE_PORT=5174"; \
		exit 1; \
	fi; \
	trap 'kill 0' INT TERM EXIT; \
	$(MAKE) env; \
	$(MAKE) db; \
	$(MAKE) wait-db; \
	PYTHONPATH=backend/src $(PYTHON_BIN) -m uvicorn silver_timeseri.api:app --host $(API_HOST) --port $(API_PORT) --reload & \
	cd frontend && npm run dev -- --host $(FE_HOST) --port $(FE_PORT) & \
	wait
