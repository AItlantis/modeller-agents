---
name: backend-contract-check
description: Validate that a backend invocation is declared through registry and contract artifacts before running it. Use before any backend run or pipeline execution request.
metadata:
  version: 0.1.0
  author: AItlantis
---

# Backend Contract Check

Before backend invocation:

1. resolve the backend id in `backends.toml`;
2. resolve the local root from `backends.local.toml` or the caller's environment;
3. read the backend-owned `backend.json`;
4. validate the manifest against the schema owned by `modeller-pipelines`;
5. check `contract.lock` compatibility when present;
6. invoke only by subprocess or declared service boundary;
7. validate `result.json` before returning it to Testudo or another caller.

Never import backend implementation code across the repository boundary.

