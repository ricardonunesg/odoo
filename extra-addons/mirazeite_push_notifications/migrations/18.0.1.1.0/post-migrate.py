def migrate(cr, version):
    # O atalho "pending_nav" deixou de existir (nada o lia); apaga os restos.
    cr.execute("DELETE FROM ir_config_parameter WHERE key LIKE 'mirazeite.pending\\_nav.%'")
