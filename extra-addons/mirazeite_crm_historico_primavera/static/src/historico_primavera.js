/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/** Texto para pesquisa: minúsculas e sem acentos. */
function normalize(text) {
    return (text || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "");
}

/** Valor em euros no formato português: -12.345,67 € */
function formatEur(value) {
    const v = Math.round((value || 0) * 100) / 100 || 0;
    const [int, dec] = Math.abs(v).toFixed(2).split(".");
    const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return `${v < 0 ? "-" : ""}${grouped},${dec} €`;
}

/**
 * Janela "Histórico Primavera" (aberta a partir da oportunidade).
 * Os dados vêm em directo do Primavera (só leitura); nada é gravado no Odoo.
 * Anos expandidos por defeito; cada documento expande/recolhe as suas linhas.
 * A pesquisa por artigo filtra no browser os dados já carregados (sem nova consulta).
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
            search: "",
            summaryYear: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        const leadId = this.props.action.params.lead_id;
        const data = await this.orm.call("crm.lead", "get_historico_primavera", [[leadId]]);
        for (const year of data.years || []) {
            for (const inv of year.invoices) {
                for (const line of inv.lines) {
                    line.searchText = normalize(`${line.code} ${line.description} ${line.article_name}`);
                }
            }
        }
        this.state.summaryYear = data.years && data.years.length ? data.years[0].year : null;
        this.state.data = data;
        this.state.loading = false;
    }

    // --- Pesquisa por artigo -------------------------------------------------

    get query() {
        return normalize(this.state.search.trim());
    }

    lineMatches(line) {
        const q = this.query;
        return Boolean(q) && line.searchText.includes(q);
    }

    /** Anos a mostrar: sem pesquisa, os originais; com pesquisa, só documentos com o artigo. */
    get visibleYears() {
        const q = this.query;
        if (!q) {
            return this.state.data.years;
        }
        return this.state.data.years.map((year) => {
            const invoices = [];
            let found = 0;
            for (const inv of year.invoices) {
                const lines = inv.lines.filter((l) => l.searchText.includes(q));
                if (lines.length) {
                    invoices.push(inv);
                    found += lines.reduce((s, l) => s + l.value, 0);
                }
            }
            return { ...year, invoices, filtered: true, foundTotal: formatEur(found) };
        });
    }

    get searchCount() {
        return this.visibleYears.reduce((s, y) => s + y.invoices.length, 0);
    }

    matchCount(inv) {
        return inv.lines.filter((l) => this.lineMatches(l)).length;
    }

    clearSearch() {
        this.state.search = "";
    }

    // --- Resumo por artigo ----------------------------------------------------

    get summary() {
        const year = this.state.data.years.find((y) => y.year === this.state.summaryYear);
        return year && year.summary;
    }

    setSummaryYear(year) {
        this.state.summaryYear = year;
    }

    // --- Expandir / recolher --------------------------------------------------

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
            for (const year of this.visibleYears) {
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
