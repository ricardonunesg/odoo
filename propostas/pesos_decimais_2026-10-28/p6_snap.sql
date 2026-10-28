select 'sol', id, peso_liquido::text, peso_bruto::text, volume::text from sale_order_line where product_id is not null
union all select 'aml', id, peso_liquido::text, peso_bruto::text, volume::text from account_move_line where display_type='product'
union all select 'pll', id, peso_liquido::text, peso_bruto::text, volume::text||'|'||pliquidot::text||'|'||pbrutot::text||'|'||volumet::text from packing_list_line
union all select 'pl', id, total_peso_liquido::text, total_peso_bruto::text, total_volume::text from packing_list
union all select 'am', id, total_peso_liquido::text, total_peso_bruto::text, total_volume::text from account_move where move_type in ('out_invoice','out_refund')
union all select 'bal', id, peso_liquido::text, peso_bruto::text, pliquidot::text||'|'||pbrutot::text from boletim_analises_linha
union all select 'ba', id, total_peso_liquido::text, total_peso_bruto::text, '' from boletim_analises
union all select 'prod', id, weight::text, volume::text, '' from product_template
order by 1,2;
