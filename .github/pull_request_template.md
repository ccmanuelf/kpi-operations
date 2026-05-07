<!--
  Pull request template — read docs/CONTRIBUTING.md for the full review
  checklist. This template enforces the "E2E Parity" rule (added after
  the entry-interface migration shipped without updating ~83 tests).
-->

## Summary

<!-- 1-3 sentences. What changed and why. The "what" should be obvious from the
diff; spend the words on the "why" — what problem does this solve? -->

## Test plan

<!-- Bullet checklist of what was tested. Include backend + frontend + e2e
where applicable. Per CLAUDE.md "verifying with the repo's existing workflow"
rule — don't invent new validation paths. -->

- [ ] Backend: `cd backend && python -m pytest tests/ --tb=short -q`
- [ ] Frontend lint + unit: `cd frontend && npm run lint && npm test`
- [ ] Frontend e2e (when frontend changes): `cd frontend && npm run test:e2e:sqlite`
- [ ] Lint + format: `flake8 . --count` returns 0; `black --check .` clean

## E2E Parity (required for any view/component change)

<!-- Per docs/CONTRIBUTING.md "E2E Parity" rule — added 2026-05-06 after
the entry-interface migration shipped without updating e2e specs and
silently broke CI for 50+ commits. -->

If this PR changes any file under `frontend/src/views/` or
`frontend/src/components/` (especially `grids/`):

- [ ] The corresponding spec(s) in `frontend/e2e/` have been **updated
      in this same PR** to match the new surface, or
- [ ] No e2e spec exists for the changed surface (note this in the
      Summary above so a reviewer can confirm), or
- [ ] The change is a no-op for e2e (pure refactor, internal-only,
      types-only) — note this in the Summary.

If this PR adds a new `test.describe.skip(...)` or `test.skip(...)`:

- [ ] Linked issue: `<paste GitHub issue URL here, or "N/A — refactor
      removed the feature">`
- [ ] Target re-enable date or removal date noted in a comment above
      the `skip` call.

If this PR is **not** a frontend change, ignore this section.

## Breaking changes

<!-- Anything that requires coordinated client-side, DB-migration, env-var,
or downstream dependency changes. Be specific. "None" if applicable. -->

## Linked issues / context

<!-- Closes #N, refs #N, supersedes #N, etc. -->
