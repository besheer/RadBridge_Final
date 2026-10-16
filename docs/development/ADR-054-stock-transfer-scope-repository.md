# ADR-054: Move stock-transfer scope queries to an infrastructure adapter

- Status: Accepted
- Date: 2026-10-16
- Scope: isolated architecture port / draft PR #2

## Context

The web extension enforced transfer visibility and destination constraints but also built SQLAlchemy subqueries for linked central warehouses, branch warehouses, and valid transfer relationships. That mixed request authorization with persistence query construction.

## Decision

Move those SQLAlchemy statements into `SqlAlchemyStockTransferScopeRepository`. The web extension composes the repository with the current Warehouse and StockTransfer models and retains HTTP permission checks, request parsing, ORM loader criteria, and denial behavior. Query rules continue to require active branch warehouses, active linked central warehouses, and a matching source-to-target parent relationship.

Legacy route handlers remain unchanged to preserve their source-identity compatibility contract. This adapter is an incremental persistence boundary, not a claim that transfer transactions have moved to an application service.

## Validation

The stock-transfer policy and branch-scope suites pass (16 tests), including valid requests, mismatched source/target denial, unauthorized central actions, transfer visibility, and foreign-branch denial. No schema, route contract, or production environment was changed.
