.PHONY: up down test test-api test-e2e perf-smoke migrate-demo

up:            ## Start the full stack
	docker compose up -d --build
	./scripts/wait-for.sh http://localhost:8000/health 90

down:          ## Stop the stack
	docker compose down -v

test: test-api ## Run every automated suite available so far

test-api:      ## API, RBAC, lifecycle and validation tests
	python -m pytest -q

test-e2e:      ## Playwright, all browsers (needs `make up`)
	cd tests/e2e && npm ci && npx playwright test

perf-smoke:    ## 30-second k6 smoke (needs `make up` and k6)
	k6 run perf/smoke.js

migrate-demo:  ## Import the legacy fixture into the Compose DB and reconcile
	docker compose cp data-migration/legacy/permits_export.csv api:/tmp/permits_export.csv
	docker compose exec api python -m permitpass.migrate_legacy /tmp/permits_export.csv --rejects /tmp/rejects.csv
