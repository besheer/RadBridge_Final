# Refund branch scope

The refund handler now enforces the same collection_policy.require_collection_branch guard as collection and receipt reprint, before reading refundable amounts or creating a refund. Cashiers must have an active account and the same branch. Reception, if explicitly granted refund permission, must additionally have collection enabled for its branch. Existing global administrator access is retained.

This fixes the cross-branch refund finding only. Refund method selection, financial closing/net-ledger behavior, concurrent refunds and malformed amount validation remain separate review items. No live refund is executed for deployment validation. Tests cover denied scopes without balance/payment mutation and preserve the allowed partial-refund/audit contract.
