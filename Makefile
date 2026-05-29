.PHONY: build dev serve docker-build docker-run export-data build-pages

dev:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

serve:
	uv run uvicorn web:app --reload

docker-build:
	docker build -t wc-match-classifier .

docker-run:
	docker run -p 8000:8000 \
		-e CORS_ORIGINS="http://localhost:5173,http://localhost:4173" \
		wc-match-classifier

export-data:
	uv run python scripts/export_matches.py

build-pages: export-data
	cd frontend && VITE_API_URL=https://wc-match-classifier.onrender.com npx vite build --mode ghpages
