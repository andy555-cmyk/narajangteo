#!/bin/bash
# 나라장터 수집 → 대시보드 빌드. 키는 .env 에서만 읽는다(git 제외).
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a
[ -z "$SERVICE_KEY" ] && { echo "!! SERVICE_KEY 없음 — .env 에 SERVICE_KEY=... 를 넣으세요"; exit 1; }
exec .venv/bin/python g2b_scan.py "$@"
