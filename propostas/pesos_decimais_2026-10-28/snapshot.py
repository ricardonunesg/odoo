"""Fotografia de uma BD de teste (só leitura) para comparar antes/depois de -u.
Uso: snapshot.py <db> <ficheiro_saida>. Cada linha: secção|chave|valor."""
import subprocess
import sys

DB, OUT = sys.argv[1], sys.argv[2]
MODS = ("primavera_connector", "documentos", "formularios", "mesprod_export_pricing",
        "mirazeite_alertas_comerciais", "mirazeite_partner_nif_dedup", "mirazeite_partner_search")
MODS_SQL = "(" + ",".join(f"'{m}'" for m in MODS) + ")"


def q(sql):
    r = subprocess.run(["docker", "exec", "odoo_test_pg", "psql", "-U", "odoo", "-d", DB, "-At", "-F", "\x1f", "-c", sql],
                       capture_output=True, text=True, check=True)
    return [line.split("\x1f") for line in r.stdout.splitlines() if line]


def rowhash(table, exclude=("write_date", "write_uid", "create_date", "create_uid")):
    ex = " ".join(f"- '{c}'" for c in exclude)
    return f"select id, md5((to_jsonb(t) {ex})::text) from {table} t"


SECTIONS = {
    "cron": "select c.id, concat_ws(' / ', c.cron_name, c.active, c.interval_number || ' ' || c.interval_type, c.nextcall, c.priority, c.user_id, md5(coalesce(s.code,''))) "
            "from ir_cron c join ir_act_server s on s.id=c.ir_actions_server_id",
    "menu": "select m.id, concat_ws(' / ', m.name::text, m.parent_id, m.action, m.sequence, m.active, m.web_icon, "
            "(select string_agg(gid::text, ',' order by gid) from ir_ui_menu_group_rel r where r.menu_id=m.id)) from ir_ui_menu m",
    "acesso": "select a.id, concat_ws(' / ', a.name, a.model_id, a.group_id, a.perm_read, a.perm_write, a.perm_create, a.perm_unlink, a.active) from ir_model_access a",
    "regra": "select r.id, concat_ws(' / ', r.name, r.model_id, md5(coalesce(r.domain_force,'')), r.perm_read, r.perm_write, r.perm_create, r.perm_unlink, r.active, r.global, "
             "(select string_agg(group_id::text, ',' order by group_id) from rule_group_rel x where x.rule_group_id=r.id)) from ir_rule r",
    "grupo": "select g.id, concat_ws(' / ', g.name::text, g.category_id, "
             "(select string_agg(hid::text, ',' order by hid) from res_groups_implied_rel i where i.gid=g.id)) from res_groups g",
    "utilizador_grupo": "select uid || '-' || gid, 'x' from res_groups_users_rel",
    "parametro": "select key, value from ir_config_parameter",
    "numeracao": "select s.id, concat_ws(' / ', s.code, s.name, s.prefix, s.padding, s.number_next, s.number_increment, s.implementation, s.use_date_range, s.active) from ir_sequence s",
    "numeracao_proximo": "select s.id, s.number_next_actual from (select id from ir_sequence) x join lateral (select 1) y on true join ir_sequence s on s.id=x.id",
    "numeracao_periodo": "select d.id, concat_ws(' / ', d.sequence_id, d.date_from, d.date_to, d.number_next) from ir_sequence_date_range d",
    "casas_decimais": "select name, digits from decimal_precision",
    "ecra": "select v.id, concat_ws(' / ', v.name, v.model, v.inherit_id, v.priority, v.mode, v.active, md5(coalesce(v.arch_db::text,''))) from ir_ui_view v",
    "accao_janela": "select a.id, concat_ws(' / ', a.name::text, a.res_model, a.view_mode, md5(coalesce(a.domain,'') || coalesce(a.context,'')), a.view_id) from ir_act_window a",
    "accao_servidor": "select a.id, concat_ws(' / ', a.name::text, a.state, md5(coalesce(a.code,''))) from ir_act_server a",
    "relatorio": "select a.id, concat_ws(' / ', a.name::text, a.report_name, a.paperformat_id) from ir_act_report_xml a",
    "imd": f"select module || '.' || name, concat_ws(' / ', model, res_id, noupdate) from ir_model_data where module in {MODS_SQL}",
}
TABLES = ["res_partner_category", "export_ecl_stage", "export_document_type", "crm_stage", "project_task_type",
          "packing_list_template", "declaracao_lote_template", "certificado_salubridade_template",
          "certificado_qualidade_template", "boletim_analises_template", "certificado_conformidade_alimentar_template",
          "certificado_organoletica_preset", "certificado_organoletica_preset_linha", "documento_morada",
          "mesprod_export_logistics_mode", "mesprod_export_raw_material_category", "mesprod_export_margin_policy",
          "mirazeite_commercial_alert_close_reason", "mirazeite_commercial_alert_config",
          "mail_template", "uom_uom", "primavera_connection", "res_company"]
COUNTS = ["sale_order", "sale_order_line", "account_move", "account_move_line", "res_partner", "product_template",
          "product_product", "project_task", "mail_message", "primavera_sync_log", "hr_employee", "res_users",
          "ir_attachment", "packing_list", "declaracao_lote", "export_ecl_document_line", "ir_model_fields", "ir_model"]

existing = {r[0] for r in q("select tablename from pg_tables where schemaname='public'")}
with open(OUT, "w") as f:
    for sec, sql in SECTIONS.items():
        if sec == "numeracao_proximo":
            # número seguinte real (sequências 'standard' vivem numa sequência do Postgres)
            for sid, impl in q("select id, implementation from ir_sequence"):
                if impl == "standard":
                    v = q(f"select last_value, is_called from ir_sequence_{int(sid):03d}")
                    f.write(f"{sec}|{sid}|{v[0][0]}:{v[0][1]}\n" if v else f"{sec}|{sid}|?\n")
            continue
        for k, v in q(sql):
            f.write(f"{sec}|{k}|{v}\n")
    for t in TABLES:
        if t in existing:
            for k, v in q(rowhash(t)):
                f.write(f"tabela:{t}|{k}|{v}\n")
    for t in COUNTS:
        if t in existing:
            f.write(f"contagem|{t}|{q(f'select count(*) from {t}')[0][0]}\n")
print("OK", OUT)
