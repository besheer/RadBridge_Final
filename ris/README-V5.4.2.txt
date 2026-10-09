RIS Web v5.4.2 Hotfix
Fixes runtime NameError and schema integration:
- Restores Attachment model
- Restores Receipt model
- Restores DeliveryEvent model
- Adds report/images delivery fields to Order ORM
- Adds attachment upload/download endpoints
- Adds persistent ./attachments:/data/attachments volume
- Makes schema ALTER statements safer with IF NOT EXISTS
- Keeps v5.4 bilingual procedure catalog and v5.4.1 payment endpoint fix
