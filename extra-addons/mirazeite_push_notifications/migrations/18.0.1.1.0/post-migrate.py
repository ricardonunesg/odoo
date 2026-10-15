from datetime import datetime


def migrate(cr, version):
    # O atalho "pending_nav" deixou de existir (nada o lia); apaga os restos.
    cr.execute("DELETE FROM ir_config_parameter WHERE key LIKE 'mirazeite.pending\\_nav.%'")
    # Marca o resumo como já enviado até agora, para a instalação não mandar
    # logo um resumo da noite anterior; o primeiro sai no fim do próximo silêncio.
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cr.execute("""
        INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
        VALUES ('mirazeite.push.last_summary', %s, 1, 1, now(), now())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = now()
    """, (now,))
