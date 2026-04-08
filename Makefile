.PHONY: setup dev pull-model test-email autoskills autoskills-dry-run

setup:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install
	cd ai-service && pip install -r requirements.txt

dev:
	docker-compose up --build

pull-model:
	docker exec -it sync-bank-ollama-1 ollama pull qwen2.5:3b

test-email:
	python scripts/send_test_email.py

autoskills:
	npx autoskills -y

autoskills-dry-run:
	npx autoskills --dry-run -y
