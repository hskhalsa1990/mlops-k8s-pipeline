## What and why

## How was it tested
- [ ] `make ci` passes (lint and tests)
- [ ] Training gate still passes (`make train`), if training or the model changed
- [ ] `make manifests` and `make lint-infra` pass, if manifests, `deploy.sh` or the Dockerfile changed

## Documentation
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Docs, runbook or ADR updated if behaviour or operations changed

## Deployment notes
- [ ] No manifest or GitHub secret/variable changes needed (or described above)
