FRONTEND := llmwiki/web/frontend

.PHONY: web-install web-build dev test eval

## Install web UI dev dependencies (run once; needs Node + npm).
web-install:
	npm --prefix $(FRONTEND) install

## Build the web UI into llmwiki/web/static (commit the result).
web-build:
	npm --prefix $(FRONTEND) run build

## Dev: FastAPI on :8000 (API) + Vite on :5173 (UI with HMR, proxies /api).
## Open http://127.0.0.1:5173 and edit src/*.ts or src/styles.css for live reload.
dev:
	@bash -c 'PYTHONPATH="$(CURDIR)" llmwiki serve --no-open & api=$$!; \
		trap "kill $$api 2>/dev/null" EXIT; \
		npm --prefix $(FRONTEND) run dev'

## Run the Python test suite.
test:
	pytest

## Run the LLM evals (faked model, no API key) — e.g. the citation-grounding eval.
eval:
	pytest tests/eval -q
