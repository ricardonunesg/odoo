/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useAutofocus, useService } from "@web/core/utils/hooks";

/** Texto para pesquisa: minúsculas e sem acentos. */
function normalize(text) {
    return (text || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "");
}

/** Lista de artigos com pesquisa (aberta pelo botão "Pesquisar Artigo"). */
class ArtigoPicker extends Component {
    static template = "mirazeite_crm_historico_primavera.ArtigoPicker";
    static props = { articles: Array, onSelect: Function, onClose: Function };

    setup() {
        this.state = useState({ query: "" });
        useAutofocus();
    }

    get filtered() {
        // Todas as palavras escritas têm de aparecer (por qualquer ordem) no código ou na descrição.
        const words = normalize(this.state.query).split(/\s+/).filter(Boolean);
        if (!words.length) {
            return this.props.articles;
        }
        return this.props.articles.filter((a) => words.every((w) => a.searchText.includes(w)));
    }

    onKeydown(ev) {
        if (ev.key === "Escape") {
            ev.stopPropagation();
            this.props.onClose();
        } else if (ev.key === "Enter" && this.filtered.length === 1) {
            this.props.onSelect(this.filtered[0].code);
        }
    }
}

/**
 * Janela "Histórico Primavera" (aberta a partir da oportunidade).
 * Os dados vêm em directo do Primavera (só leitura); nada é gravado no Odoo.
 * Anos expandidos por defeito; cada documento expande/recolhe as suas linhas.
 * "Pesquisar Artigo" mostra os movimentos de um artigo a partir dos dados já carregados,
 * sem nova consulta e sem alterar a lista de documentos.
 */
export class HistoricoPrimavera extends Component {
    static template = "mirazeite_crm_historico_primavera.Historico";
    static components = { ArtigoPicker };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            data: null,
            closedYears: {},
            openInvoices: {},
            pickerOpen: false,
            article: null, // código do artigo seleccionado
        });
        onWillStart(() => this.load());
    }

    async load() {
        const leadId = this.props.action.params.lead_id;
        const data = await this.orm.call("crm.lead", "get_historico_primavera", [[leadId]]);
        // Artigos vendidos ao cliente (sem duplicados), para a lista "Pesquisar Artigo".
        const articles = new Map();
        for (const year of data.years || []) {
            for (const inv of year.invoices) {
                for (const line of inv.lines) {
                    if (!line.is_article) {
                        continue;
                    }
                    if (!articles.has(line.code)) {
                        articles.set(line.code, {
                            code: line.code,
                            name: line.article_name || line.description,
                            texts: new Set([line.code, line.article_name]),
                        });
                    }
                    articles.get(line.code).texts.add(line.description);
                }
            }
        }
        this.articles = [...articles.values()]
            .map((a) => ({ code: a.code, name: a.name, searchText: normalize([...a.texts].join(" ")) }))
            .sort((a, b) => a.code.localeCompare(b.code));
        this.state.data = data;
        this.state.loading = false;
    }

    // --- Pesquisar Artigo -----------------------------------------------------

    togglePicker() {
        this.state.pickerOpen = !this.state.pickerOpen;
    }

    selectArticle(code) {
        this.state.article = code;
        this.state.pickerOpen = false;
    }

    backToHistory() {
        this.state.article = null;
        this.state.pickerOpen = false;
    }

    get selectedArticle() {
        return this.articles.find((a) => a.code === this.state.article);
    }

    /** Movimentos do artigo seleccionado, do mais recente para o mais antigo. */
    get movements() {
        const code = this.state.article;
        const rows = [];
        for (const year of this.state.data.years) {
            for (const inv of year.invoices) {
                for (const line of inv.lines) {
                    if (line.is_article && line.code === code) {
                        rows.push({ key: line.id, inv, line });
                    }
                }
            }
        }
        return rows; // documentos já vêm ordenados por data desc (ano atual primeiro)
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
