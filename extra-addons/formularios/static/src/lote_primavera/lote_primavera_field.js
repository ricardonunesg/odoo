/** @odoo-module **/
// Campo Lote: ao clicar mostra os lotes do artigo faturados ao cliente (Primavera, só leitura) e, ao escrever, filtra.
// O lote pode ser sempre escrito à mão (useInputField grava o texto, como num campo normal).
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useChildRef, useService } from "@web/core/utils/hooks";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { useInputField } from "@web/views/fields/input_field_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class LotePrimaveraField extends Component {
    static template = "formularios.LotePrimaveraField";
    static components = { AutoComplete };
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.input = useChildRef();
        this.consulta = { chave: null, lotes: [], mensagem: "" };
        useInputField({ ref: this.input, getValue: () => this.valor });
    }

    get valor() {
        return this.props.record.data[this.props.name] || "";
    }

    get fontes() {
        return [{
            placeholder: "A consultar o Primavera…",
            optionTemplate: "formularios.LotePrimaveraOpcao",
            options: (pesquisa) => this.opcoes(pesquisa),
        }];
    }

    async consultar() {
        const linha = this.props.record;
        const cliente = linha._parentRecord && linha._parentRecord.data.cliente_partner_id;
        const artigo = linha.data.codigo_artigo;
        if (!cliente || !artigo) {
            return { chave: null, lotes: [], mensagem: "Escolha primeiro o cliente e o artigo, ou escreva o lote." };
        }
        const chave = `${cliente[0]}|${artigo}`;
        if (this.consulta.chave !== chave) {
            try {
                const r = await this.orm.silent.call("form.reclama.cliente.linha", "lotes_vendidos_primavera", [artigo, cliente[0]]);
                this.consulta = { chave, lotes: r.lotes, mensagem: r.mensagem };
            } catch {
                return { chave: null, lotes: [], mensagem: "Primavera indisponível — escreva o lote." };
            }
        }
        return this.consulta;
    }

    async opcoes(pesquisa) {
        const { lotes, mensagem } = await this.consultar();
        const texto = pesquisa.toLowerCase();
        const encontrados = lotes.filter((l) => l.lote.toLowerCase().includes(texto));
        if (encontrados.length) {
            return encontrados.map((l) => ({ label: l.lote, ...l }));
        }
        return !texto && mensagem ? [{ label: mensagem, mensagem: true }] : [];
    }

    escolher(opcao) {
        if (!opcao.mensagem) {
            this.props.record.update({ [this.props.name]: opcao.lote });
        }
    }
}

export const lotePrimaveraField = { component: LotePrimaveraField, supportedTypes: ["char"] };
registry.category("fields").add("lote_primavera", lotePrimaveraField);
