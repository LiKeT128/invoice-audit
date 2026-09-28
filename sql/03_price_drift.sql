-- Monthly price against the contract, and against the previous month.
-- LAG is the check: the contract price never moved, the invoice price did.

SELECT
  strftime('%Y-%m', i.invoice_date) AS month,
  i.qty,
  i.unit_eur,
  v.contract_unit_eur,
  i.unit_eur - v.contract_unit_eur AS gap_eur,
  (i.unit_eur - v.contract_unit_eur) * i.qty AS overcharge_eur,
  i.unit_eur - LAG(i.unit_eur) OVER (ORDER BY i.invoice_date) AS change_vs_prior_month_eur
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
WHERE v.name = 'Danube Hosting s.r.o.'
  AND i.sku = 'SEAT-HOST'
ORDER BY i.invoice_date;
