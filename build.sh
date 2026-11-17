#!/usr/bin/env bash
# Build Render : s'arrête à la première erreur
set -o errexit

pip install -r requirements.txt

# Tailwind autonome (sans Node.js), version figée pour des builds reproductibles
TAILWIND_VERSION="v4.3.1"
curl -sSfL -o tailwindcss "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64"
chmod +x tailwindcss
./tailwindcss -i static/src/tailwind.css -o static/css/tailwind.css --minify

# Le CSS doit exister AVANT collectstatic
python manage.py collectstatic --no-input
python manage.py migrate