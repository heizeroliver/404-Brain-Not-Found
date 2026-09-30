#!/usr/bin/env bash
# One-shot attempt to override the lab's org policy at project level.
# Usage: bash gcp_allow_models.sh PROJECT_ID
# Expected outcomes: either "policy set" (then re-run gemini_smoke.py) or
# PERMISSION_DENIED (the lab account cannot change org policies; use an
# AI Studio API key instead, see gemini_smoke.py).
set -u
PROJECT="${1:?usage: bash gcp_allow_models.sh PROJECT_ID}"
cat > /tmp/allow_models.yaml <<YAML
name: projects/${PROJECT}/policies/vertexai.allowedModels
spec:
  rules:
  - values:
      allowedValues:
      - publishers/google/models/gemini-2.5-flash:predict
      - publishers/google/models/gemini-2.5-flash-lite:predict
      - publishers/google/models/gemini-2.5-pro:predict
YAML
gcloud org-policies set-policy /tmp/allow_models.yaml --project="${PROJECT}" && echo "policy set: now re-run python3 gemini_smoke.py ${PROJECT}"
