/** @odoo-module **/
// Link "Abrir no Responder" das notificações: abre a lista da Qualidade e, por cima, a janela do Responder
// (a mesma do botão da lista). Não cria nem grava respostas; ao fechar, fica-se na lista.
import { registry } from "@web/core/registry";

const ACOES = {
    cliente: ["action_qualidade_cliente", "action_abrir_responder_cliente"],
    fornecedor: ["action_qualidade_fornecedor", "action_abrir_responder_fornecedor"],
    interna: ["action_qualidade_interna", "action_abrir_responder_fornecedor"],
};

async function abrirResponder(env, action) {
    const { tipo, reclamacao } = action.params;
    const [lista, responder] = ACOES[tipo] || ACOES.cliente;
    await env.services.action.doAction(`qualidade_reclamacoes.${lista}`);
    await env.services.action.doAction(`qualidade_reclamacoes.${responder}`, {
        additionalContext: { active_id: Number(reclamacao) },
    });
}

registry.category("actions").add("qualidade_abrir_responder", abrirResponder);
