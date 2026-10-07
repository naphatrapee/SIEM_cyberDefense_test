.PHONY: up down logs seed test demo geoip reset
up:
	@test -f .env || cp .env.example .env
	docker compose up --build -d
down:
	docker compose down
logs:
	docker compose logs -f --tail=100
seed:
	python samples/post_logs.py
	bash samples/send_syslog.sh
test:
	pytest -q tests
demo: up seed
geoip:
	bash scripts/get_geoip.sh
reset:   # wipe the database volume (re-runs db/*.sql on next start)
	docker compose down -v
