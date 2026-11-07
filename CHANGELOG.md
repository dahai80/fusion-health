---
doc_id: fusion-health/changelog
product: fusion-health
class: app
entry: service
doc_type: changelog
title: { zh: "变更日志", en: "Changelog" }
audience: engineer
status: draft
version: 1.2.6
updated: 2026-11-07
owner: @dahai
source_of_truth:
  - CHANGELOG.md
  - README.md
---

# Changelog

All notable changes to fusion-health are documented here. The
release-by-release history through v1.2.6 lives in README.md ("Changelog"
section); this file tracks changes going forward in Keep-a-Changelog format.

## [Unreleased]

### Added
- Adopted the fusion docs-system v1.1 contract (grid position app x service):
  `docs/product-page.md`, `docs/get-started.md`, `docs/api-reference.md`,
  `docs/config-reference.md`, `docs/architecture.md`, `docs/troubleshooting.md`,
  `CHANGELOG.md`, 12-key frontmatter on in-scope markdown, and CI validation
  via `ci/validate_docs.py` gating markdown PRs (`.github/workflows/docs.yml`).
