.PHONY: up down test test-api test-e2e perf-smoke

up:            ## Start the full stack
	docker compose up -d --build
	./scripts/wait-for.sh http://localhost:8000/health 90

down:          ## Stop the stack
	docker compose down -v

test: test-api ## Run every automated suite available so far

test-api:      ## API, RBAC, lifecycle and validation tests
	python -m pytest -q

test-e2e:      ## Playwright (needs `make up`)
	cd tests/e2e && npx playwright test

perf-smoke:    ## 30-second k6 smoke (needs `make up` and k6)
	k6 run perf/smoke.js
