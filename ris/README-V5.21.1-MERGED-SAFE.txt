RIS v5.21.1 MERGED SAFE

Base features: v5.21 RIS Studio.
Production hotfixes merged from ris-web-CURRENT-HOTFIXED.tar.gz.

Preserved regression fixes:
1. SQLAlchemy and_ import required by smart_booking_cards / Booking Board.
2. device_booking_reason(device, start_at=None, end_at=None) compatible with
   schedule_v2 one-argument calls and booking-slot calls.
3. DeviceBlock query does NOT reference the nonexistent DeviceBlock.active column.

Do not deploy without backup. After deployment run the full smoke test.
