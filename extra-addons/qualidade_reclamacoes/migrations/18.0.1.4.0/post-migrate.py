"""Volta a preencher os 8 valores guardados (mesma regra, directamente na base de dados), depois de o
módulo estar carregado. Garante valores certos mesmo que as colunas já existissem (ex.: nova aplicação
depois de uma reversão), sem alterar o "Modificado por/em" das reclamações.
"""
import importlib.util
import os


def migrate(cr, version):
    caminho = os.path.join(os.path.dirname(__file__), 'pre-migrate.py')
    spec = importlib.util.spec_from_file_location('qualidade_reclamacoes_pre_migrate_1_4_0', caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo.preencher(cr)
