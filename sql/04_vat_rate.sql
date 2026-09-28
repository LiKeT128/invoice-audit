-- Booked VAT rate against the vendor master.
-- After 1 Jan 2025 the standard Slovak rate is 23%. A 20% booking is the old rate.

SELECT
  v.name AS vendor,
  i.invoice_no,
  i.invoice_date,
  i.net_eur,
  i.booked_vat_bps,
  v.vat_bps,
  i.net_eur * (v.vat_bps - i.booked_vat_bps) / 10000 AS vat_gap_eur
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
WHERE i.booked_vat_bps <> v.vat_bps
ORDER BY vat_gap_eur DESC;
