RIS Web v5.4.1 Hotfix
=======================
Fixes:
- Flask startup crash caused by duplicate endpoint function name add_payment.
- Receipt-based payment endpoint renamed to receive_payment.
- Uses existing payments.create permission consistently.
- Order Detail page cleaned of duplicated payment/delivery sections.
- Order Detail now receives payments, receipts, attachments and delivery history explicitly.
- Keeps v5.4 bilingual 222-procedure catalog and all existing database data.

Upgrade does not require a database reset.
