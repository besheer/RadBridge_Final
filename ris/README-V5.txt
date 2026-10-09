RIS Web v5.0 - Operations / Admin / Auto-MWL
=================================================

Major changes
-------------
1. Patient ID is generated automatically as P00000001, P00000002, ...
2. Reception no longer sees AE Title, DICOM port, or Worklist fields.
3. Reception selects:
   - Patient
   - Branch
   - Procedure
   - Contract/Payer
   - Schedule
   - Payment
4. RIS automatically:
   - generates Accession Number
   - resolves modality from Procedure Catalog
   - chooses the active device by Branch + Modality + Priority
   - gets the AE Title from Admin device configuration
   - creates the Orthanc MWL entry
5. Admin Panel:
   - Users
   - Roles & granular permissions
   - Branches
   - Devices / AE Titles
   - Procedure Catalog
   - Contracts & procedure-specific pricing
   - Inventory / consumables
   - Audit Log
6. Predefined roles:
   SUPER_ADMIN, IT, RECEPTION, CALL_CENTER, NURSING, TECHNICIAN,
   SERVICE, RADIOLOGIST, CASHIER, CONTRACTS, INVENTORY, MANAGEMENT
7. Contract calculations:
   gross price, contract price, patient share, company share.
8. Payments:
   CASH, VISA, MASTERCARD, WALLET, BANK_TRANSFER.
   Multiple payment entries allow split payment.
9. Consumables:
   procedure default consumables are copied to the order automatically.
   When technician marks COMPLETED, default quantities are deducted once.
10. Reporting v4 flow remains available.

Initial administrator
---------------------
Username: admin
Password: ChangeMe_RIS_Admin_2026

CHANGE THIS PASSWORD IMMEDIATELY after first login:
Sidebar -> Change password

Upgrade from v4.2
-----------------
Keep backups until v5 is tested.

cd /opt/ris-pacs
docker compose -f ris-web/docker-compose.ris.yml down
mv ris-web ris-web-v4.2-backup
mkdir ris-web
tar -xzf /home/hawary/ris-web-v5.tar.gz -C ris-web --strip-components=1

Restore persistent data:
cp -a ris-web-v4.2-backup/ris-db ris-web/
if [ -d ris-web-v4.2-backup/report-files ]; then
  cp -a ris-web-v4.2-backup/report-files ris-web/
fi

Start:
cd /opt/ris-pacs/ris-web
docker compose -f docker-compose.ris.yml up -d --build

Check:
docker ps | grep -E 'ris-web|ris-pacs'
curl https://ris.dynuddns.net/api/reporting/health

First configuration before real reception use
----------------------------------------------
1. Login as admin.
2. Change admin password.
3. Admin Panel -> Branches: add all branches.
4. Admin Panel -> Devices / AE Titles:
   add each CT/MR/DX/CR/US/MG device with Branch, AE Title, IP, Port and Priority.
5. Admin Panel -> Users:
   create staff users and assign roles.
6. Admin Panel -> Roles & Permissions:
   adjust permissions if required.
7. Procedure Catalog:
   starter exam list is preloaded. Add/edit site-specific procedures/prices as required.
8. Contracts:
   add payers and their co-pay rules; then open Price List for procedure-specific prices.
9. Inventory:
   starter contrast consumables are preloaded.

Important
---------
The v5 schema updater adds nullable columns to the existing patient/order tables and creates new master tables.
Do not delete the v4.2 backup until patient registration, order routing, MWL, billing and reporting have all been tested.
