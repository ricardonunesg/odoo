# Listas partilhadas pelas respostas da Qualidade, pelas reclamações e pelos painéis.
# Mudar um valor aqui muda-o em todos os sítios que o usam.
from odoo.addons.formularios.models.constantes import ARMAZENS, INSTALACOES  # noqa: F401

ESTADOS_RESPOSTA = [
    ('aberto', 'Aberto'),
    ('pendente', 'Pendente'),
    ('fechado', 'Fechado'),
]

CATEGORIAS = [
    ('qualidade', 'Qualidade'),
    ('seguranca', 'Segurança'),
    ('servico', 'Serviço (Transporte)'),
]

# Origem do problema: as mesmas instalações das reclamações internas
ORIGENS = INSTALACOES

GRAVIDADES = [
    ('baixa', 'Baixa'),
    ('media', 'Média'),
    ('alta', 'Alta'),
    ('critica', 'Crítica'),
]
