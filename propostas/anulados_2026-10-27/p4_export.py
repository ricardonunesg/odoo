# Só leitura: respostas reais da WebAPI de uma amostra de clientes/fornecedores, para o ensaio isolado.
import json, random
c = env["primavera.connection"].browse(1)
P = env["res.partner"].sudo().with_context(active_test=False)
partilhadas = P.search([("primavera_customer_code", "!=", False), ("primavera_supplier_code", "!=", False)], order="id", limit=3)
codes = {"FO0160", "FO0792", "CL0027", "CL0056", "CL0062", "CL0063"}
codes |= set(partilhadas.mapped("primavera_customer_code")) | set(partilhadas.mapped("primavera_supplier_code"))
random.seed(27)
codes |= set(random.sample(P.search([("primavera_customer_code", "=like", "CL%")]).mapped("primavera_customer_code"), 15))
codes |= set(random.sample(P.search([("primavera_supplier_code", "=like", "FO%")]).mapped("primavera_supplier_code"), 15))
api = {}
for code in sorted(codes):
    base = "/v2/Base/Clientes" if code.startswith("CL") else "/v2/Base/Fornecedores"
    api[code] = c._edita(f"{base}/Edita/{code}", strict=True)
json.dump({"api": api, "partilhadas": [[p.id, p.primavera_customer_code, p.primavera_supplier_code] for p in partilhadas]},
          open("/tmp/p4_dados.json", "w"), default=str)
print("R respostas gravadas:", len(api), "| inactivos:", [k for k, v in api.items() if v and v.get("Inactivo")], "| partilhadas:", [[p.primavera_customer_code, p.primavera_supplier_code] for p in partilhadas])
