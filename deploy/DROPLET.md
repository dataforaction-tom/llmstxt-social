# Droplet Quick Start (Single-VM Docker)

This repo runs best on a droplet using `docker-compose.single.yml`.
The default `docker-compose.yml` is for local development.

## First-time setup

```bash
git clone https://github.com/dataforaction-tom/llmstxt-social.git
cd llmstxt-social
cp .env.example .env
# edit .env with production values (keep POSTGRES_PASSWORD consistent)

docker compose -f docker-compose.single.yml up -d --build
docker compose -f docker-compose.single.yml exec api alembic upgrade head
```

## Switching from the dev compose file

```bash
./deploy/scripts/switch-to-single.sh /opt/llmstxt-social
```

## Updates

```bash
./deploy/scripts/update-stack.sh /opt/llmstxt-social
```

## Important

- Avoid `docker compose down -v` in production; it deletes the DB volume and resets credentials.
