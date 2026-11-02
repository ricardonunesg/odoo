import re

from odoo import api, models

# Rastreabilidade de um lote de produto acabado (reclamações de clientes), lida do Primavera no momento:
# nada é gravado no Odoo e todas as consultas são SELECT (formularios.primavera.leitura recusa o resto).
# Regras decididas com a Qualidade (02/11/2026):
# - produção e materiais: só os consumos reais das COM, filtrados pela linha do produto reclamado
#   (IdLinhaComposto), nunca a ficha técnica; data de produção = data da COM;
# - origem dos materiais até 2 níveis (lotações internas), com aviso de mistura;
# - destinos: só faturas FA/FAT/FRT (linhas reais, não anuladas); devoluções à parte;
#   guias com lote sem fatura do mesmo cliente → aviso de rastreabilidade incompleta.

FATURAS = ('FA', 'FAT', 'FRT')
DEVOLUCOES = ('NC', 'NCT', 'DEV')
GUIAS = ('GR', 'GRT', 'GT')
ENTRADAS_INTERNAS = ('ES', 'AIP')
CLIENTE_INTERNO = 'CL0000'
LIMITE = 200            # máximo de linhas por bloco (mais do que isso → aviso)
LIMITE_ENTRADAS = 20    # entradas por lote de material
NIVEIS_ORIGEM = 2


def _lote_generico(lote):
    return not lote or lote.startswith('<')


def _ph(n):
    return ', '.join(['%s'] * n)


SQL_PRODUCOES = """
    SELECT TOP 50 e.Id, c.Serie, c.NumDoc, c.Data, e.Quantidade, e.Armazem, c.Id
    FROM INV_LinhasComposicoes e
    JOIN INV_CabecComposicoes c ON c.Id = e.IdCabecComposicoes
    WHERE c.TipoDoc = 'COM' AND e.EntradaSaida = 'E' AND e.Artigo = %s AND e.Lote = %s
    ORDER BY c.Data, c.NumDoc"""

SQL_CONSUMOS = """
    SELECT TOP {limite} s.Artigo, MAX(a.Descricao), s.Lote, SUM(s.Quantidade), MAX(s.Unidade)
    FROM INV_LinhasComposicoes s
    LEFT JOIN Artigo a ON a.Artigo = s.Artigo
    WHERE s.EntradaSaida = 'S' AND s.IdLinhaComposto IN ({ids})
    GROUP BY s.Artigo, s.Lote
    ORDER BY s.Artigo, s.Lote"""

SQL_COMPRAS = """
    SELECT TOP %d c.TipoDoc, c.Serie, c.NumDoc, c.Entidade, c.Nome, ISNULL(l.DataEntrada, c.DataDoc), ABS(l.Quantidade),
           CAST(l.Id AS varchar(40)),
           (SELECT TOP 1 CAST(t.IdLinhasComprasOrigem AS varchar(40)) FROM LinhasComprasTrans t WHERE t.IdLinhasCompras = l.Id)
    FROM LinhasCompras l
    JOIN CabecCompras c ON c.Id = l.IdCabecCompras
    JOIN DocumentosCompra d ON d.Documento = c.TipoDoc
    LEFT JOIN CabecComprasStatus s ON s.IdCabecCompras = c.Id
    WHERE l.Artigo = %%s AND l.Lote = %%s AND l.Quantidade <> 0
      AND d.LigaStocks = 1 AND c.TipoDoc NOT IN ('NDM', 'NDMT') AND ISNULL(s.Anulado, 0) = 0
    ORDER BY ISNULL(l.DataEntrada, c.DataDoc)""" % (LIMITE_ENTRADAS + 1)

SQL_INTERNOS = """
    SELECT TOP %d c.TipoDoc, c.Serie, c.NumDoc, c.Data, ABS(l.Quantidade)
    FROM LinhasInternos l
    JOIN CabecInternos c ON c.Id = l.IdCabecInternos
    WHERE l.Artigo = %%s AND l.Lote = %%s AND c.TipoDoc IN ('ES', 'AIP') AND ISNULL(c.Anulado, 0) = 0 AND l.Quantidade <> 0
    ORDER BY c.Data""" % LIMITE_ENTRADAS

SQL_DOCS_VENDA = """
    SELECT TOP {limite} c.TipoDoc, c.Serie, c.NumDoc, c.Data, c.Entidade, c.Nome,
           c.EntidadeEntrega, ce.Nome, l.Quantidade
    FROM LinhasDoc l
    JOIN CabecDoc c ON c.Id = l.IdCabecDoc
    LEFT JOIN CabecDocStatus s ON s.IdCabecDoc = c.Id
    LEFT JOIN Clientes ce ON ce.Cliente = c.EntidadeEntrega
    WHERE c.TipoDoc IN ({tipos}) AND ISNULL(s.Anulado, 0) = 0
      AND l.Artigo = %s AND l.Lote = %s AND l.Quantidade <> 0
    ORDER BY c.Data, c.NumDoc"""

SQL_GUIAS_SEM_FATURA = """
    SELECT TOP 50 c.TipoDoc, c.Serie, c.NumDoc, c.Data, c.Entidade, c.Nome, l.Quantidade
    FROM LinhasDoc l
    JOIN CabecDoc c ON c.Id = l.IdCabecDoc
    LEFT JOIN CabecDocStatus s ON s.IdCabecDoc = c.Id
    WHERE c.TipoDoc IN ('GR', 'GRT', 'GT') AND c.Entidade <> 'CL0000' AND ISNULL(s.Anulado, 0) = 0
      AND l.Artigo = %s AND l.Lote = %s AND l.Quantidade > 0
      AND NOT EXISTS (
          SELECT 1 FROM LinhasDoc f
          JOIN CabecDoc cf ON cf.Id = f.IdCabecDoc
          LEFT JOIN CabecDocStatus sf ON sf.IdCabecDoc = cf.Id
          WHERE cf.TipoDoc IN ('FA', 'FAT', 'FRT') AND ISNULL(sf.Anulado, 0) = 0
            AND cf.Entidade = c.Entidade AND f.Artigo = l.Artigo AND f.Lote = l.Lote)
    ORDER BY c.Data"""

SQL_OUTROS_PA = """
    SELECT TOP %d e.Artigo, MAX(a.Descricao), e.Lote, c.Serie, c.NumDoc, MAX(c.Data), SUM(s.Quantidade)
    FROM INV_LinhasComposicoes s
    JOIN INV_LinhasComposicoes e ON e.Id = s.IdLinhaComposto
    JOIN INV_CabecComposicoes c ON c.Id = s.IdCabecComposicoes
    LEFT JOIN Artigo a ON a.Artigo = e.Artigo
    WHERE c.TipoDoc = 'COM' AND s.EntradaSaida = 'S' AND s.Artigo = %%s AND s.Lote = %%s
    GROUP BY e.Artigo, e.Lote, c.Serie, c.NumDoc
    ORDER BY MAX(c.Data), c.NumDoc""" % (LIMITE + 1)

# lotes produzidos com este material que voltam a ser consumidos noutras COM (lotações intermédias)
SQL_INTERMEDIOS = """
    SELECT DISTINCT x.Artigo, x.Lote
    FROM INV_LinhasComposicoes x
    WHERE x.EntradaSaida = 'S' AND EXISTS (
        SELECT 1 FROM INV_LinhasComposicoes s
        JOIN INV_LinhasComposicoes e ON e.Id = s.IdLinhaComposto
        WHERE s.EntradaSaida = 'S' AND s.Artigo = %s AND s.Lote = %s AND e.Artigo = x.Artigo AND e.Lote = x.Lote)"""

SQL_CLIENTES_OUTROS_PA = """
    SELECT l.Artigo, l.Lote, c.Entidade, MAX(c.Nome), SUM(l.Quantidade), COUNT(DISTINCT c.Id)
    FROM LinhasDoc l
    JOIN CabecDoc c ON c.Id = l.IdCabecDoc
    LEFT JOIN CabecDocStatus s ON s.IdCabecDoc = c.Id
    WHERE c.TipoDoc IN ('FA', 'FAT', 'FRT') AND ISNULL(s.Anulado, 0) = 0 AND l.Quantidade > 0
      AND EXISTS (
          SELECT 1 FROM INV_LinhasComposicoes sc
          JOIN INV_LinhasComposicoes ec ON ec.Id = sc.IdLinhaComposto
          WHERE sc.EntradaSaida = 'S' AND sc.Artigo = %s AND sc.Lote = %s
            AND ec.Artigo = l.Artigo AND ec.Lote = l.Lote)
    GROUP BY l.Artigo, l.Lote, c.Entidade
    ORDER BY l.Artigo, l.Lote, c.Entidade"""


class QualidadeRastreabilidade(models.AbstractModel):
    _name = 'qualidade.rastreabilidade'
    _description = 'Rastreabilidade de lotes (Primavera, só leitura)'

    # ---------- auxiliares ----------

    def _coms_apagadas(self, ler):
        """COM eliminadas no Primavera (ferramenta DelAZ): ficam no Primavera mas não contam.
        Devolve {(serie, numdoc)}; serie None = número a excluir em qualquer série."""
        apagadas = set()
        for (tabela,) in ler.q("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE %s",
                               'Codex_Backup_INV_CabecComposicoes_COM%_Del%'):
            if not re.fullmatch(r'[A-Za-z0-9_]+', tabela):
                continue
            try:
                apagadas.update((str(s), int(n)) for s, n in ler.q("SELECT Serie, NumDoc FROM [%s] WHERE TipoDoc = 'COM'" % tabela))
            except Exception:
                m = re.search(r'_COM(\d+)_', tabela)
                if m:
                    apagadas.add((None, int(m.group(1))))
        return apagadas

    @staticmethod
    def _sem_faturas_de_guias(compras):
        """A V/Fatura (VFA/VFAT) e a V/Guia (VGR/VGRT) do mesmo fornecimento movem ambas stock: a fatura não conta
        como outra entrada. Correspondência CONFIRMADA quando o Primavera liga a linha da fatura à da guia
        (LinhasComprasTrans); sem essa ligação, mesmo fornecedor e quantidade até 60 dias = PROVÁVEL (assinalada)."""
        linhas = [[t, s, n, e, nome, d, q, None, lid, origem] for t, s, n, e, nome, d, q, lid, origem in compras]
        guias = [g for g in linhas if g[0] in ('VGR', 'VGRT')]
        por_id = {g[8]: g for g in guias}
        resultado = []
        for linha in linhas:
            t, s, n, e, _nome, d, q, _fat, _lid, origem = linha
            if t in ('VFA', 'VFAT'):
                guia = por_id.get(origem)
                if guia and not guia[7]:
                    guia[7] = 'fatura %s %s/%s' % (t, s, n)
                    continue
                guia = next((g for g in guias if not g[7] and g[3] == e and abs((g[6] or 0) - (q or 0)) < 0.001
                             and d and g[5] and abs((d - g[5]).days) <= 60), None)
                if guia:
                    guia[7] = 'fatura provável %s %s/%s' % (t, s, n)
                    continue
            resultado.append(linha)
        return resultado

    @staticmethod
    def _apagada(apagadas, serie, numdoc):
        return (str(serie), int(numdoc)) in apagadas or (None, int(numdoc)) in apagadas

    def _producoes(self, ler, artigo, lote, apagadas):
        return [{'id': str(i), 'com': 'COM %s/%s' % (serie, num), 'data': data, 'quantidade': qtd,
                 'armazem': arm, 'cabec': str(cab)}
                for i, serie, num, data, qtd, arm, cab in ler.q(SQL_PRODUCOES, artigo, lote)
                if not self._apagada(apagadas, serie, num)]

    def _consumos(self, ler, producoes):
        ids = [p['id'] for p in producoes]
        if not ids:
            return [], False
        linhas = ler.q(SQL_CONSUMOS.format(limite=LIMITE + 1, ids=_ph(len(ids))), *ids)
        return [{'artigo': a, 'descricao': d or '', 'lote': (l or '').strip(), 'quantidade': q, 'unidade': u or '',
                 'generico': _lote_generico((l or '').strip())}
                for a, d, l, q, u in linhas[:LIMITE]], len(linhas) > LIMITE

    def _origem(self, ler, artigo, lote, apagadas, nivel=1):
        """De onde veio um lote de material: compras (fornecedor, documento, data de receção), lotação interna
        (COM que o produziu, com os lotes de origem até 2 níveis) ou entrada interna (stock inicial/acerto)."""
        compras = self._sem_faturas_de_guias(ler.q(SQL_COMPRAS, artigo, lote))
        if compras:
            return {'tipo': 'compra', 'mistura': len(compras) > 1, 'excesso': len(compras) > LIMITE_ENTRADAS,
                    'entradas': [{'documento': '%s %s/%s' % (t, s, n) + (' (+ %s)' % fat if fat else ''),
                                  'fornecedor': '%s %s' % (e or '', nome or ''), 'data': d, 'quantidade': q}
                                 for t, s, n, e, nome, d, q, fat, _lid, _origem in compras[:LIMITE_ENTRADAS]]}
        lotacoes = self._producoes(ler, artigo, lote, apagadas)
        if lotacoes:
            origem = {'tipo': 'lotacao', 'producoes': lotacoes, 'componentes': [], 'limite': False}
            if nivel < NIVEIS_ORIGEM:
                componentes, _excesso = self._consumos(ler, lotacoes)
                for comp in componentes:
                    comp['origem'] = None if comp['generico'] else self._origem(ler, comp['artigo'], comp['lote'], apagadas, nivel + 1)
                origem['componentes'] = componentes
                origem['mistura'] = len({(c['artigo'], c['lote']) for c in componentes if not c['generico']}) > 1
            else:
                origem['limite'] = True
            return origem
        internas = ler.q(SQL_INTERNOS, artigo, lote)
        if internas:
            return {'tipo': 'interna', 'entradas': [{'documento': '%s %s/%s' % (t, s, n), 'data': d, 'quantidade': q}
                                                    for t, s, n, d, q in internas]}
        return {'tipo': 'desconhecida'}

    def _docs_venda(self, ler, tipos, artigo, lote):
        linhas = ler.q(SQL_DOCS_VENDA.format(limite=LIMITE + 1, tipos=_ph(len(tipos))), *tipos, artigo, lote)
        docs = [{'documento': '%s %s/%s' % (t, s, n), 'data': d, 'cliente': '%s %s' % (e or '', nome or ''),
                 'entrega': ('%s %s' % (ee, nome_e or '')) if ee and ee != e else '', 'quantidade': q}
                for t, s, n, d, e, nome, ee, nome_e, q in linhas[:LIMITE]]
        return docs, len(linhas) > LIMITE

    # ---------- consultas usadas pelo ecrã ----------

    @api.model
    def consultar(self, artigo, lote):
        """Bloco 1 (produção), 2 (materiais deste produto, com origem) e 3 (clientes do lote)."""
        artigo, lote = (artigo or '').strip(), (lote or '').strip()
        r = {'artigo': artigo, 'lote': lote, 'producoes': [], 'outros_na_com': 0, 'materiais': [],
             'clientes': [], 'devolucoes': [], 'guias_sem_fatura': [], 'avisos': []}
        if not artigo or not lote:
            r['avisos'].append("Esta linha não tem artigo e lote preenchidos.")
            return r
        with self.env['formularios.primavera.leitura']._ligacao() as ler:
            apagadas = self._coms_apagadas(ler)
            r['producoes'] = self._producoes(ler, artigo, lote, apagadas)
            if r['producoes']:
                cabecs = sorted({p['cabec'] for p in r['producoes']})
                r['outros_na_com'] = ler.q(
                    "SELECT COUNT(*) FROM INV_LinhasComposicoes WHERE EntradaSaida = 'E' AND Artigo IS NOT NULL"
                    " AND IdCabecComposicoes IN (%s) AND NOT (Artigo = %%s AND Lote = %%s)" % _ph(len(cabecs)),
                    *cabecs, artigo, lote)[0][0]
                r['materiais'], excesso = self._consumos(ler, r['producoes'])
                if excesso:
                    r['avisos'].append("Mais de %d materiais: só os primeiros são apresentados." % LIMITE)
                if not r['materiais']:
                    r['avisos'].append("A COM não tem consumos registados para este produto.")
                for m in r['materiais']:
                    m['origem'] = None if m['generico'] else self._origem(ler, m['artigo'], m['lote'], apagadas)
            elif ler.q("SELECT COUNT(*) FROM ArtigoLote WHERE Artigo = %s AND Lote = %s", artigo, lote)[0][0]:
                r['avisos'].append("O lote existe no Primavera, mas não foi encontrada nenhuma COM que o tenha produzido.")
            else:
                r['avisos'].append("Lote não encontrado no Primavera para este artigo (pode ter sido escrito de outra forma).")
            r['clientes'], excesso = self._docs_venda(ler, FATURAS, artigo, lote)
            if excesso:
                r['avisos'].append("Mais de %d faturas: só as primeiras são apresentadas." % LIMITE)
            r['devolucoes'], _excesso = self._docs_venda(ler, DEVOLUCOES, artigo, lote)
            r['guias_sem_fatura'] = [{'documento': '%s %s/%s' % (t, s, n), 'data': d, 'cliente': '%s %s' % (e, nome or ''),
                                      'quantidade': q} for t, s, n, d, e, nome, q in ler.q(SQL_GUIAS_SEM_FATURA, artigo, lote)]
            if r['guias_sem_fatura']:
                r['avisos'].append("Há expedições (guias) deste lote sem fatura do mesmo cliente: a lista de clientes pode estar incompleta.")
        r['clientes_distintos'] = len({c['cliente'] for c in r['clientes']})
        r['quantidade_faturada'] = sum(c['quantidade'] for c in r['clientes'])
        return r

    @api.model
    def outros_produtos(self, artigo, lote):
        """Outros lotes de produto acabado que consumiram este lote de material, com os clientes (faturas)."""
        artigo, lote = (artigo or '').strip(), (lote or '').strip()
        r = {'artigo': artigo, 'lote': lote, 'produtos': [], 'avisos': [], 'descricao': ''}
        if _lote_generico(lote):
            r['avisos'].append("Lote genérico — rastreabilidade não disponível.")
            return r
        with self.env['formularios.primavera.leitura']._ligacao() as ler:
            apagadas = self._coms_apagadas(ler)
            desc = ler.q("SELECT Descricao FROM Artigo WHERE Artigo = %s", artigo)
            r['descricao'] = desc[0][0] if desc else ''
            linhas = [x for x in ler.q(SQL_OUTROS_PA, artigo, lote)
                      if not self._apagada(apagadas, x[3], x[4])]
            if len(linhas) > LIMITE:
                r['avisos'].append("Mais de %d produções: só as primeiras são apresentadas." % LIMITE)
            intermedios = set(ler.q(SQL_INTERMEDIOS, artigo, lote))
            if intermedios:
                r['avisos'].append("Rastreabilidade de destino potencialmente incompleta: %d lote(s) produzido(s) com este "
                                   "material (lotações intermédias) foram depois consumidos noutras produções, que não são "
                                   "seguidas até aos produtos acabados." % len(intermedios))
            clientes = {}
            for a, l, e, nome, q, ndocs in ler.q(SQL_CLIENTES_OUTROS_PA, artigo, lote):
                clientes.setdefault((a, l), []).append({'cliente': '%s %s' % (e, nome or ''), 'quantidade': q, 'documentos': ndocs})
            r['produtos'] = [{'artigo': a, 'descricao': d or '', 'lote': l, 'com': 'COM %s/%s' % (s, n), 'data': data,
                              'consumo': q, 'clientes': clientes.get((a, l), []), 'intermedio': (a, l) in intermedios}
                             for a, d, l, s, n, data, q in linhas[:LIMITE]]
        return r
