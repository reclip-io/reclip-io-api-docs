# Reclip API documentation

English Mintlify documentation for Reclip Public API v1. This repository contains the OpenAPI snapshot, resource references, 30 server-tool guides, runnable examples and an LLM skill.

## Status

Public beta. Published at https://reclip.io/docs. The application proxies /docs to the reclip-io Mintlify project. API and MCP access require a scoped workspace key and an active paid subscription. Provider availability is determined by live catalogs and job results.

## Preview and validation

Run `npx mint dev` to preview, `npx mint validate` and `npx mint broken-links` for Mintlify checks, and `python3 scripts/check_docs.py` for repository checks.

## Contract source

The main reclip-io repository exports this snapshot from runtime domain schemas with `yarn build:domain && node scripts/export-public-api-docs.mjs /path/to/reclip-io-api-docs`. Regenerate after a contract change. Tool schemas preserve server validation; some cross-field refinements are enforced only at runtime.

Publishing this repository does not configure hosting or DNS.
