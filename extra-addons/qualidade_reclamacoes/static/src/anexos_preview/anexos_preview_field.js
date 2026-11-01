/** @odoo-module **/
// Lista de anexos da ficha do Responder com pré-visualização: igual ao campo many2many_binary do Odoo,
// mas imagens, PDF, vídeo e texto abrem no visualizador de ficheiros nativo do Odoo (o mesmo do Projects).
// Os restantes formatos (Excel, Word, ZIP, links do Google Drive…) continuam a descarregar/abrir como antes.
import { registry } from "@web/core/registry";
import {
    Many2ManyBinaryField,
    many2ManyBinaryField,
} from "@web/views/fields/many2many_binary/many2many_binary_field";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { FileModel } from "@web/core/file_viewer/file_model";
import { onWillDestroy } from "@odoo/owl";

export class QualidadeAnexosPreviewField extends Many2ManyBinaryField {
    static template = "qualidade_reclamacoes.AnexosPreviewField";

    setup() {
        super.setup();
        this.fileViewer = useFileViewer();
        // Esc com o visualizador aberto fecha SÓ o visualizador (sem isto fechava também a ficha do Responder
        // e perdia-se o que não estava gravado). Com o visualizador fechado, o Esc segue o comportamento do Odoo.
        this.onEscVisualizador = (ev) => {
            const fechar = ev.key === "Escape" && document.querySelector(".o-FileViewer-header .fa-times");
            if (!fechar) {
                return;
            }
            ev.preventDefault();
            ev.stopImmediatePropagation();
            fechar.closest(".o-FileViewer-headerButton").click(); // o mesmo que o botão ✕ (qualquer das listas)
        };
        window.addEventListener("keydown", this.onEscVisualizador, true);
        onWillDestroy(() => window.removeEventListener("keydown", this.onEscVisualizador, true));
    }

    ficheiroDoVisualizador(file) {
        return Object.assign(new FileModel(), { id: file.id, name: file.name, mimetype: file.mimetype });
    }

    podeVer(file) {
        return this.ficheiroDoVisualizador(file).isViewable;
    }

    onCliqueAnexo(ev, file) {
        if (!this.podeVer(file)) {
            return; // descarrega como sempre
        }
        ev.preventDefault();
        const todos = this.files.map((f) => this.ficheiroDoVisualizador(f));
        this.fileViewer.open(todos.find((f) => f.id === file.id), todos);
    }
}

export const qualidadeAnexosPreviewField = {
    ...many2ManyBinaryField,
    component: QualidadeAnexosPreviewField,
};

registry.category("fields").add("qualidade_anexos_preview", qualidadeAnexosPreviewField);
