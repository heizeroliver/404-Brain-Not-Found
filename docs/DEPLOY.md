# Deploying Kate Foresight on Cloud Run

One container serves the API and the app (`/app/`) from the same origin. It listens on `0.0.0.0:$PORT`.
Everything runs from Google Cloud Shell; no credentials are needed on a laptop, and no key files are created.

## Steps (Cloud Shell)

```bash
git clone https://github.com/heizeroliver/404-Brain-Not-Found && cd 404-Brain-Not-Found
gcloud config set project <PROJECT_ID>
# optional voice ids (not secrets):
export ELEVENLABS_VOICE_NL=<voice-id> ELEVENLABS_VOICE_EN=<voice-id> ELEVENLABS_VOICE_FR=<voice-id>
bash scripts/deploy_cloud_run.sh                    # in-memory state
STORAGE=firestore bash scripts/deploy_cloud_run.sh  # durable goals, consents, advisor requests
```

The script:
- enables Cloud Run, Cloud Build, Artifact Registry and Secret Manager (plus Firestore when `STORAGE=firestore`);
- creates the runtime service account `kate-foresight-run` and grants it `secretAccessor` on the Kate secrets only, and `roles/datastore.user` only in Firestore mode;
- stores `kate-jwt-secret`, `kate-demo-password` and `kate-admin-password` in Secret Manager. They are generated once and reused, so every instance signs with the same JWT secret;
- prompts, with hidden input, for the ElevenLabs key (`kate-elevenlabs-key`). The value is piped on stdin, so it never appears in arguments or history;
- deploys to `europe-west1` with `--min-instances 1 --max-instances 1`, then calls `/health`.

Read the passwords (these print to your terminal only):
`gcloud secrets versions access latest --secret kate-demo-password` (and `kate-admin-password`).

## Verify the deployment

1. Open `<URL>/app/` and log in as lien. Overview and charts should load.
2. `curl <URL>/health` should return `{"status":"ok"}`. It reports no configuration and no secrets.
3. Logging in as lien and calling an `/admin/v2/...` route should return 403.
4. Only with `STORAGE=firestore`: save a goal, redeploy or restart, and the goal should still be there.

## After the event

```bash
gcloud run services update kate-foresight --region europe-west1 --min-instances 0
```

## What is durable and what is not

| State | Memory mode | Firestore mode |
|---|---|---|
| Synthetic customers (baseline, 203) | image | image |
| Goals, consents, advisor requests | lost on restart | Firestore |
| Feedback, delivery frequency caps, rules added in Rule studio, decision log, rate limits | per process | per process |

Because some state is still per process, the service stays capped at **one instance**. It is not ready for unrestricted autoscaling.
The benchmark (10,000 customers, one process, `docs/BENCHMARK.md`) is measured. The 2.3M-customer architecture in the README is a proposal, not a deployment.
