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
python manage.py collectstatic --no-input --ignore=src/tailwind.css
python manage.py migrate

# Compte de démonstration remis à neuf à chaque déploiement (si DEMO_PASSWORD est défini).
# "|| echo" : un souci sur la démo ne doit jamais bloquer la mise en ligne.
if [ -n "${DEMO_PASSWORD:-}" ]; then
  python manage.py creer_demo || echo "Attention : compte de démonstration non réinitialisé."
fi