-- Two invoices, one vendor, a few days apart.
-- Each stays under the single-signature limit. Together they cross it.

SELECT
  v.name AS vendor,
  a.invoice_no AS first_no,
  b.invoice_no AS second_no,
  a.invoice_date AS first_date,
  b.invoice_date AS second_date,
  a.net_eur AS first_net_eur,
  b.net_eur AS second_net_eur,
  a.net_eur + b.net_eur AS combined_net_eur,
  v.solo_limit_eur
FROM invoices a
JOIN invoices b
  ON a.vendor_id = b.vendor_id
 AND a.id < b.id
 AND a.invoice_no <> b.invoice_no
 AND julianday(b.invoice_date) - julianday(a.invoice_date) BETWEEN 0 AND 6
JOIN vendors v ON v.id = a.vendor_id
WHERE a.net_eur < v.solo_limit_eur
  AND b.net_eur < v.solo_limit_eur
  AND a.net_eur + b.net_eur > v.solo_limit_eur
  AND a.net_eur > v.solo_limit_eur * 0.40
  AND b.net_eur > v.solo_limit_eur * 0.40
ORDER BY combined_net_eur DESC;
