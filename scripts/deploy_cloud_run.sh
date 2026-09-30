#!/usr/bin/env bash
# Deploy Kate Foresight to Cloud Run from Google Cloud Shell.
#   git clone https://github.com/heizeroliver/404-Brain-Not-Found && cd 404-Brain-Not-Found
#   bash scripts/deploy_cloud_run.sh
# Secrets are generated here and set on the service; they are printed once and never written to the repo.
set -euo pipefail
PROJECT="$(gcloud config get-value project 2>/dev/null)"
REGION="${REGION:-europe-west1}"   # St-Ghislain, Belgium
SERVICE="${SERVICE:-kate-foresight}"
echo "Project: $PROJECT  Region: $REGION  Service: $SERVICE"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

JWT_SECRET="$(openssl rand -base64 48 | tr -d '\n/+=')"
DEMO_PASSWORD="kate-$(openssl rand -hex 4)"
ADMIN_PASSWORD="admin-$(openssl rand -hex 6)"

gcloud run deploy "$SERVICE" --source . --region "$REGION" --allow-unauthenticated \
  --memory 512Mi --max-instances 3 \
  --set-env-vars "APP_ENV=production,DEMO_TODAY=2026-09-30,JWT_SECRET=${JWT_SECRET},DEMO_PASSWORD=${DEMO_PASSWORD},ADMIN_PASSWORD=${ADMIN_PASSWORD}"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo
echo "App:            ${URL}/app/"
echo "Customer login: lien / marc / rita  with password ${DEMO_PASSWORD}"
echo "Admin login:    admin  with password ${ADMIN_PASSWORD}"
echo "Keep these passwords out of git and out of the video."
