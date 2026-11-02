/** @odoo-module **/
// Campo Lote com botão de lotes faturados ao cliente (Primavera, só leitura). O lote continua a poder ser escrito à mão.
import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { CharField, charField } from "@web/views/fields/char/char_field";

export class LotePrimaveraField extends CharField {
    static template = "formularios.LotePrimaveraField";
    static components = { ...CharField.components, Dropdown, DropdownItem };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.lotes = useState({ itens: [], mensagem: "" });
    }

    escolherLote(l) {
        this.props.record.update({ [this.props.name]: l.lote });
    }

    async carregarLotes() {
        const linha = this.props.record;
        const cliente = linha._parentRecord && linha._parentRecord.data.cliente_partner_id;
        this.lotes.itens = [];
        if (!cliente || !linha.data.codigo_artigo) {
            this.lotes.mensagem = "Escolha primeiro o cliente e o artigo.";
            return;
        }
        this.lotes.mensagem = "A consultar o Primavera…";
        try {
            const r = await this.orm.call("form.reclama.cliente.linha", "lotes_vendidos_primavera", [linha.data.codigo_artigo, cliente[0]]);
            this.lotes.itens = r.lotes;
            this.lotes.mensagem = r.mensagem;
        } catch {
            this.lotes.mensagem = "Primavera indisponível — escreva o lote.";
        }
    }
}

export const lotePrimaveraField = { ...charField, component: LotePrimaveraField };
registry.category("fields").add("lote_primavera", lotePrimaveraField);
