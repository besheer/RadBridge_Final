RIS v5.27.1 Finance Rules & Approvals

Built on v5.27 Management / Referral Analytics.

Adds:
- Performing Doctor Share Rules: percent/fixed, by doctor/branch/modality/procedure/contract.
- Calculation basis: Gross, Contract Price, or Net After Approved Discount.
- Explicit Performing Doctor assignment per order; falls back to active Case Assignment.
- Discount Policies by Role/User/Branch/Procedure/Contract.
- Max Direct Discount and Max Discount Request thresholds.
- Reception/Cashier can request discounts only when granted finance.discount.request.
- Direct discount requires finance.discount.apply and policy limit.
- Management approval queue requires finance.discount.approve.
- Policy maintenance requires finance.discount.manage.
- Doctor share maintenance/view use finance.doctor_share.manage / finance.doctor_share.view.
- Approved discounts reduce order balance.
- Payment is stopped while a discount request is pending, preventing collection against an unapproved net price.
- Doctor Earnings report includes Revenue, Discount, Net, Share.
- All decisions and applications are audited.
- New permissions appear in Admin Roles.

All v5.27 and v5.26 Golden functionality remains present.
