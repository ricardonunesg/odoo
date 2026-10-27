from . import documento_morada
from . import ir_sequence  # número de documento sem repetir
from . import res_company
from . import product_ext
from . import certificado_organoletica
from . import certificado_narrativo_abstract
from . import packing_list_template
from . import packing_list
from . import account_move_ext
from . import declaracao_lote        # inclui DeclaracaoLoteTemplate
from . import certificado_salubridade  # inclui CertificadoSalubridadeTemplate
from . import certificado_qualidade    # inclui CertificadoQualidadeTemplate
from . import certificado_conformidade # inclui CertificadoConformidadeTemplate
from . import boletim_analises         # inclui BoletimAnalisesTemplate
# Documentação de Exportação (módulo fundido)
from . import export_document_type
from . import export_ecl_stage
from . import export_ecl
from . import sale_order_ext
from . import res_partner
# Deve ser carregado depois de todos os modelos concretos referenciados
from . import mixin_no_customer_followers
