import json
c = env["primavera.connection"].browse(1)
codes = ["CL0027", "CL0056", "CL0062", "CL0063", "CL0109", "CL0128", "CL0119", "CL0137", "CL0171", "CL0181", "CL0455", "CL0760",
         "CL0090", "CL0101", "CL0864", "CL0873", "CL0647", "FO0743", "FO0028"]
p4 = json.load(open("/tmp/p4_dados.json"))["api"]
api = {}
for code in codes:
    base = "/v2/Base/Clientes" if code.startswith("CL") else "/v2/Base/Fornecedores"
    api[code] = c._edita(f"{base}/Edita/{code}", strict=True)
for k, v in p4.items():
    api.setdefault(k, v)
json.dump(api, open("/tmp/p5_api.json", "w"), default=str)
print("R respostas:", len(api), "| NIF:", {k: (v.get("NumContribuinte") or v.get("NumContrib"), v.get("Pais")) for k, v in api.items() if k in codes[:12]})
