"""Smoke test for Gemini on the team's Google Cloud project.

Run in Cloud Shell (already authenticated) or on a laptop after
`gcloud auth application-default login`:

    pip install -q google-genai
    python3 gemini_smoke.py [PROJECT_ID]

It tries a few locations and model names and prints the first combination
that answers, plus the lines to put in backend/.env. No secrets are needed.
"""
import os
import subprocess
import sys

LOCATIONS = ["europe-west1", "global", "us-central1"]
MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-pro", "gemini-2.5-flash"]
PROMPT = "Zeg hallo in het Nederlands en het Frans, in een zin."


def project_id() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    for var in ("GCP_PROJECT", "GOOGLE_CLOUD_PROJECT", "DEVSHELL_PROJECT_ID"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        out = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True, text=True, check=True, timeout=20,
        ).stdout.strip()
        if out and out != "(unset)":
            return out
    except Exception:  # noqa: BLE001 - best effort only
        pass
    sys.exit("No project id found. Run: python3 gemini_smoke.py <PROJECT_ID>")


def main() -> None:
    try:
        from google import genai
    except ImportError:
        sys.exit("Run first: pip install -q google-genai")

    project = project_id()
    print(f"Project: {project}")
    for location in LOCATIONS:
        client = genai.Client(vertexai=True, project=project, location=location)
        for model in MODELS:
            try:
                reply = client.models.generate_content(model=model, contents=PROMPT)
                text = (reply.text or "").strip()
            except Exception as exc:  # noqa: BLE001 - we want to keep trying
                msg = str(exc).splitlines()[0][:110]
                print(f"  {location:14s} {model:18s} -> no ({msg})")
                continue
            print(f"  {location:14s} {model:18s} -> OK: {text[:120]}")
            print("\nPut these in backend/.env:")
            print(f"GCP_PROJECT={project}")
            print(f"GCP_LOCATION={location}")
            print(f"GEMINI_MODEL={model}")
            return
    sys.exit("\nNothing worked. Check that the Agent Platform API is enabled and that you are authenticated.")


if __name__ == "__main__":
    main()
