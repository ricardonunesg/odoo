/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Janela "Histórico Primavera" (aberta a partir da oportunidade).
 * Os dados vêm em directo do Primavera (só leitura); nada é gravado no Odoo.
 * Anos expandidos por defeito; cada fatura expande/recolhe as suas linhas.
 */
export class HistoricoPrimavera extends Component {
    static template = "mirazeite_crm_historico_primavera.Historico";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            data: null,
            closedYears: {},
            openInvoices: {},
        });
        onWillStart(() => this.load());
    }

    async load() {
        const leadId = this.props.action.params.lead_id;
        this.state.data = await this.orm.call("crm.lead", "get_historico_primavera", [[leadId]]);
        this.state.loading = false;
    }

    isYearOpen(year) {
        return !this.state.closedYears[year];
    }

    toggleYear(year) {
        this.state.closedYears[year] = !this.state.closedYears[year];
    }

    toggleInvoice(id) {
        this.state.openInvoices[id] = !this.state.openInvoices[id];
    }

    setAllInvoices(open) {
        const opened = {};
        if (open) {
            for (const year of this.state.data.years) {
                for (const inv of year.invoices) {
                    opened[inv.id] = true;
                }
            }
        }
        this.state.openInvoices = opened;
        this.state.closedYears = {};
    }
}

registry.category("actions").add("mirazeite_crm_historico_primavera.historico", HistoricoPrimavera);
