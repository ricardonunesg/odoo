{
    'name': 'Mirazeite — Lembrete de Atividades',
    'version': '18.0.1.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'Lembrete às 08:00 (Lisboa) de cada atividade com prazo para hoje, '
               'pelo canal escolhido por cada utilizador (Discuss ou email)',
    'description': """
Lembrete diário de atividades
=============================
* Todos os dias, a partir das 08:00 (hora de Lisboa), cada responsável recebe
  um aviso por cada atividade com prazo nesse dia (CRM, To-Do, Projetos, ...).
* O aviso vai pelo canal que cada utilizador escolheu nas preferências
  (Caixa de entrada do Discuss ou email) — nada é forçado.
* Fica ligado ao registo da atividade: o nome é clicável e abre o registo.
* Um só aviso por atividade e por dia, sem repetições. Atividades criadas
  depois das 08:00 já tiveram o aviso de atribuição e não recebem lembrete.
""",
    'depends': ['mail'],
    'data': [
        'data/cron.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
