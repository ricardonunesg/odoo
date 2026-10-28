select so.id, so.name, so.partner_id, so.partner_invoice_id, so.partner_shipping_id, so.user_id, so.team_id, so.fiscal_position_id, so.pricelist_id, so.payment_term_id, so.state, so.stage_id,
 (select count(*) from export_ecl_document_line l where l.sale_order_id=so.id), (select count(*) from mail_message m where m.model='sale.order' and m.res_id=so.id),
 (select count(*) from mail_followers f where f.res_model='sale.order' and f.res_id=so.id), coalesce(so.primavera_fatura_refs,'')
from sale_order so where so.primavera_ecl_ref is not null order by so.id;
