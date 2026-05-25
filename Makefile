.PHONY: build serve

build:
	cd frontend && npm run build

serve:
	uv run uvicorn web:app --reload
