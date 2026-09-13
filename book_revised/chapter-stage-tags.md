# Chapter Stage Tags

This file records the Git references used by the book's hands-on workflow. The companion source repository is located at `D:\personal\repos\alpha` in the current development environment.

## Chapter 1

| Tag | Commit | Purpose |
|---|---|---|
| `chapter-01-start` | `279a11a2b199bb2f30dba341b5ad6d125d5382cf` | Intentionally empty project from which the reader creates the React application |
| `chapter-01-complete` | `ec9635c7d96e0cab1cdf172ba48529df7e0a614b` | Verified frontend shell with ticker validation, explicit UI states, mocked results, reset behavior, and a visible job ID |

The completion commit is on the local `book-stages` branch. It is derived from the original Phase 1 frontend at commit `43d4f28dc97ab4ae4cd70c54fa6769e826a4ed2f`, with the current product name and visible job ID added to satisfy the revised chapter contract.

Both chapter tags are annotated tags. Commands such as `git show-ref --tags` may display each tag object's ID instead of the commit ID recorded above. Resolve the underlying commit with:

```powershell
git rev-parse "chapter-01-start^{commit}"
git rev-parse "chapter-01-complete^{commit}"
```

To inspect the curated chapter history:

```powershell
git log --oneline --decorate chapter-01-start..chapter-01-complete
git diff chapter-01-start chapter-01-complete -- frontend
```

## Chapter 2

| Tag | Commit | Purpose |
|---|---|---|
| `chapter-02-start` | `ec9635c7d96e0cab1cdf172ba48529df7e0a614b` | Completed Chapter 1 frontend with a mocked timer and no backend API |
| `chapter-02-complete` | `5156b79fc27d9df1f8a72f02a6d515ea9e83a349` | FastAPI job contract, temporary in-memory status, server-side validation, focused API tests, CORS, and bounded frontend polling |

Both Chapter 2 tags are annotated. Resolve and inspect them with:

```powershell
git rev-parse "chapter-02-start^{commit}"
git rev-parse "chapter-02-complete^{commit}"
git log --oneline --decorate chapter-02-start..chapter-02-complete
git diff chapter-02-start chapter-02-complete
```

## Chapter 3

| Tag | Commit | Purpose |
|---|---|---|
| `chapter-03-start` | `5156b79fc27d9df1f8a72f02a6d515ea9e83a349` | Completed Chapter 2 API with process-local jobs and no separate worker |
| `chapter-03-local-complete` | `f26a2714ea9c9b4a8f5a9dd98a00818a5e07d0bd` | SQLite-backed queue, separate local worker, and focused persistence and claim tests used by the Chapter 3 narrative |
| `chapter-03-complete` | `a2effa48bad2636d286269a16251bc91ba38905f` | Deployment-ready PostgreSQL and Service Bus job path, separate API and worker images, focused tests, Container Apps configuration, and immutable commit-SHA image workflow |

The Chapter 3 tags are annotated. Resolve and inspect them with:

```powershell
git rev-parse "chapter-03-start^{commit}"
git rev-parse "chapter-03-local-complete^{commit}"
git rev-parse "chapter-03-complete^{commit}"
git diff chapter-03-start chapter-03-local-complete -- backend/api
```

## Publication Status

The `book-stages` branch and chapter tags currently exist only in the local companion repository. They have not been pushed to its remote. Publish them only when explicitly requested.

Chapters 1 through 3 now have curated start and completion tags. Do not create or revise tags for Chapter 4 until Chapter 3 has been reviewed and explicitly approved.