#!/bin/sh
set -eu
export NEXTDO_DATA=/data
export NEXTDO_TZ=Europe/Rome
exec /opt/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8095
