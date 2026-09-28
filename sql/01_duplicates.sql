-- Same vendor, same invoice number, same gross, two rows.
-- The later row is the one that should not have been paid.

SELECT
  v.name AS vendor,
  a.invoice_no,
  a.invoice_date AS first_date,
  b.invoice_date AS second_date,
  a.gross_eur AS gross_eur
FROM invoices a
JOIN invoices b
  ON a.vendor_id = b.vendor_id
 AND a.invoice_no = b.invoice_no
 AND a.gross_eur = b.gross_eur
 AND a.id < b.id
JOIN vendors v ON v.id = a.vendor_id
ORDER BY a.gross_eur DESC;
