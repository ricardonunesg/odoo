{
    "name": "Tarefas (Templates + Agenda) - Odoo 18",
    "version": "18.0.1.0.0",
    "depends": ["project"],
    "installable": True,
    "application": True,
    "data": [
        "security/mail_activity_all_users_project_crm_rule.xml",
        "security/project_task_all_users_private_rule.xml",
        "security/project_task_admin_private_rule.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/tarefas_menu.xml",
        "views/tarefas_template_views.xml",
    ],
}
