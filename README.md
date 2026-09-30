# 404-Brain-Not-Found
Hackathon repo — Tectonic Hackathon 2026, KBC case.

Start here: [ACTION_PLAN.md](ACTION_PLAN.md) (concept, roles, timeline, security checklist, video script, sources).

Concept options to choose from: [CONCEPT_OPTIONS.md](CONCEPT_OPTIONS.md).

## Run the demo

```bash
./run.sh            # creates .venv and backend/.env (with a generated demo password), starts API :8000 + frontend :5173
```

Then open http://localhost:5173, pick a persona (Lien, Marc, Rita) or the admin control room, and
log in with the demo password printed by `run.sh` (also in `backend/.env`, git-ignored).

Manual steps, tests, Gemini/ElevenLabs setup and the security design: [backend/README.md](backend/README.md).
The frontend is a single file with no build step: [frontend/index.html](frontend/index.html)
(API base URL at the top of the file).
