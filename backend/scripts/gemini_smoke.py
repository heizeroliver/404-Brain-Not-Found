"""Smoke test for Gemini on the team's Google Cloud project.

Run in Cloud Shell (already authenticated) or on a laptop after
`gcloud auth application-default login`:

    pip install -q google-genai
    python3 gemini_smoke.py [PROJECT_ID]

It (1) prints the organisation policy that restricts models, if readable,
(2) tries several locations and real model names, and (3) prints the first
combination that answers plus the lines to put in backend/.env.
"""
import json
import os
import subprocess
import sys

LOCATIONS = ["europe-west1", "us-central1", "global"]
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-001",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    "gemini-3.0-flash",
    "gemini-flash-latest",
    "gemini-1.5-flash-002",
]
PROMPT = "Zeg hallo in het Nederlands en het Frans, in een zin."


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=40).stdout.strip()
    except Exception:  # noqa: BLE001 - best effort only
        return ""


def project_id() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    for var in ("GCP_PROJECT", "GOOGLE_CLOUD_PROJECT", "DEVSHELL_PROJECT_ID"):
        if os.environ.get(var):
            return os.environ[var]
    out = run(["gcloud", "config", "get-value", "project"])
    if out and out != "(unset)":
        return out
    sys.exit("No project id found. Run: python3 gemini_smoke.py <PROJECT_ID>")


def show_policy(project: str) -> None:
    print("\nEffective org policy for vertexai.allowedModels (if readable):")
    out = run(["gcloud", "org-policies", "describe", "vertexai.allowedModels",
               f"--project={project}", "--effective", "--format=json"])
    if not out:
        out = run(["gcloud", "resource-manager", "org-policies", "describe",
                   "constraints/vertexai.allowedModels", f"--project={project}",
                   "--effective", "--format=json"])
    if not out:
        print("  (could not read it; that is fine, we will probe models instead)")
        return
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        print(out[:1500])
        return
    print(json.dumps(data, indent=2)[:3000])


def try_api_key() -> bool:
    """Gemini Developer API path (Google AI Studio key), independent of the GCP org policy."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return False
    from google import genai

    client = genai.Client(api_key=key)
    print("GEMINI_API_KEY found: testing the Gemini Developer API (no GCP project needed).")
    try:
        names = [m.name.split("/")[-1] for m in client.models.list()]
        print("  Models visible with this key: " + ", ".join(names[:40]))
    except Exception as exc:  # noqa: BLE001
        print(f"  (could not list models: {str(exc)[:160]})")
        names = []
    candidates = [n for n in names if "flash" in n and "image" not in n and "tts" not in n and "live" not in n]
    for model in candidates[:6] + ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            reply = client.models.generate_content(model=model, contents=PROMPT)
            print(f"  {model:28s} -> OK: {(reply.text or '').strip()[:120]}")
            print("\nPut these in backend/.env (key stays out of git):")
            print("GEMINI_API_KEY=<your key>")
            print(f"GEMINI_MODEL={model}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"  {model:28s} -> no ({str(exc).splitlines()[0][:100]})")
    return False


def main() -> None:
    try:
        from google import genai
    except ImportError:
        sys.exit("Run first: pip install -q google-genai")

    if try_api_key():
        return

    project = project_id()
    print(f"Project: {project}")
    show_policy(project)
    print("\nProbing models:")
    policy_shown = False
    for location in LOCATIONS:
        client = genai.Client(vertexai=True, project=project, location=location)
        for model in MODELS:
            try:
                reply = client.models.generate_content(model=model, contents=PROMPT)
                text = (reply.text or "").strip()
            except Exception as exc:  # noqa: BLE001 - we want to keep trying
                full = str(exc)
                short = full.splitlines()[0][:90]
                print(f"  {location:12s} {model:24s} -> no ({short})")
                if "Organization Policy" in full and not policy_shown:
                    policy_shown = True
                    print("\n  FULL POLICY ERROR (send this to Claude):\n  " + full[:1200] + "\n")
                continue
            print(f"  {location:12s} {model:24s} -> OK: {text[:120]}")
            print("\nPut these in backend/.env:")
            print(f"GCP_PROJECT={project}")
            print(f"GCP_LOCATION={location}")
            print(f"GEMINI_MODEL={model}")
            return
    sys.exit("\nNothing worked. Send the FULL POLICY ERROR above to Claude.")


if __name__ == "__main__":
    main()
