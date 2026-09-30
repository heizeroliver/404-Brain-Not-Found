#!/usr/bin/env bash
# Deploy Kate Foresight to Cloud Run from Google Cloud Shell (steps and rollback: docs/DEPLOY.md).
#   git clone https://github.com/heizeroliver/404-Brain-Not-Found && cd 404-Brain-Not-Found
#   bash scripts/deploy_cloud_run.sh                  # in-memory state, 1 instance
#   STORAGE=firestore bash scripts/deploy_cloud_run.sh  # goals, consents, advisor requests in Firestore
#
# Secrets live in Secret Manager. Values are generated here or read with a hidden prompt and piped
# on stdin, so they never appear in command arguments, shell history or the repo.
# The runtime uses a dedicated service account (no key files) with access to only these secrets
# and, with STORAGE=firestore, the Firestore user role.
set -euo pipefail
PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
[ -n "$PROJECT" ] || { echo "No project. Run: gcloud config set project <PROJECT_ID>"; exit 1; }
REGION="${REGION:-europe-west1}"          # St-Ghislain, Belgium
SERVICE="${SERVICE:-kate-foresight}"
STORAGE="${STORAGE:-memory}"              # memory | firestore
MIN_INSTANCES="${MIN_INSTANCES:-1}"       # 1 = warm during recording; set 0 afterwards
SA_NAME="${SA_NAME:-kate-foresight-run}"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
echo "Project: $PROJECT  Region: $REGION  Service: $SERVICE  Storage: $STORAGE"

APIS="run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com"
if [ "$STORAGE" = firestore ]; then APIS="$APIS firestore.googleapis.com"; fi
gcloud services enable $APIS

gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --display-name "Kate Foresight runtime"

# ------------------------------------------------------------------ secrets
# put_secret NAME  (value on stdin); creates the secret once, adds a version, grants only the runtime SA
put_secret() {
  local name="$1"
  gcloud secrets describe "$name" >/dev/null 2>&1 || gcloud secrets create "$name" --replication-policy=automatic >/dev/null
  gcloud secrets versions add "$name" --data-file=- >/dev/null
  gcloud secrets add-iam-policy-binding "$name" --member "serviceAccount:$SA" \
    --role roles/secretmanager.secretAccessor >/dev/null
}
have_secret() { gcloud secrets versions list "$1" --filter="state=enabled" --limit=1 --format="value(name)" 2>/dev/null | grep -q .; }

# signing secret and passwords: generated once, reused on later deploys (same secret across instances)
have_secret kate-jwt-secret || openssl rand -base64 48 | tr -d '\n/+=' | put_secret kate-jwt-secret
have_secret kate-demo-password || { printf 'kate-%s' "$(openssl rand -hex 4)" | put_secret kate-demo-password; NEW_PW=1; }
have_secret kate-admin-password || { printf 'admin-%s' "$(openssl rand -hex 6)" | put_secret kate-admin-password; NEW_PW=1; }
SECRETS="JWT_SECRET=kate-jwt-secret:latest,DEMO_PASSWORD=kate-demo-password:latest,ADMIN_PASSWORD=kate-admin-password:latest"

if ! have_secret kate-elevenlabs-key; then
  read -rsp "ElevenLabs API key (Enter to skip voice): " EL_KEY; echo
  if [ -n "$EL_KEY" ]; then printf '%s' "$EL_KEY" | put_secret kate-elevenlabs-key; fi
  unset EL_KEY
fi
if have_secret kate-elevenlabs-key; then SECRETS="$SECRETS,ELEVENLABS_API_KEY=kate-elevenlabs-key:latest"; fi

# voice ids are not secrets; pass them as plain env vars if set in the shell
ENV_VARS="APP_ENV=production,DEMO_TODAY=2026-09-30,STORAGE=${STORAGE},GOOGLE_CLOUD_PROJECT=${PROJECT}"
for v in ELEVENLABS_VOICE_NL ELEVENLABS_VOICE_EN ELEVENLABS_VOICE_FR; do
  if [ -n "${!v:-}" ]; then ENV_VARS="$ENV_VARS,$v=${!v}"; fi
done

if [ "$STORAGE" = firestore ]; then
  gcloud firestore databases describe --database="(default)" >/dev/null 2>&1 || \
    gcloud firestore databases create --location="$REGION" --type=firestore-native
  gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" \
    --role roles/datastore.user --condition=None >/dev/null
fi

# max 1 instance: rate limits, feedback, deliveries and added rules are still per process (docs/DEPLOY.md)
gcloud run deploy "$SERVICE" --source . --region "$REGION" --allow-unauthenticated \
  --service-account "$SA" --memory 512Mi --cpu 1 \
  --min-instances "$MIN_INSTANCES" --max-instances 1 \
  --set-env-vars "$ENV_VARS" --set-secrets "$SECRETS"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo
echo "App:    ${URL}/app/"
echo "Health: $(curl -fsS "${URL}/health" || echo 'health check FAILED')"
echo "Logins: lien / marc / rita and admin. Passwords are in Secret Manager:"
echo "  gcloud secrets versions access latest --secret kate-demo-password"
echo "  gcloud secrets versions access latest --secret kate-admin-password"
if [ "${NEW_PW:-}" = 1 ]; then echo "(new passwords were generated in this run)"; fi
echo "After recording: gcloud run services update $SERVICE --region $REGION --min-instances 0"
