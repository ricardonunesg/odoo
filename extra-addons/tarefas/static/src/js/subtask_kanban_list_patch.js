/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProjectTaskStateSelection } from "@project/components/project_task_state_selection/project_task_state_selection";
import { SubtaskKanbanList } from "@project/components/subtask_kanban_list/subtask_kanban_list";

patch(ProjectTaskStateSelection.prototype, {
    get isToggleMode() {
        return this.props.isToggleMode;
    },
});

patch(SubtaskKanbanList.prototype, {
    async _onSubtaskCreateNameChanged(name) {
        const projectId = this.props.record.data.project_id?.[0] || false;
        const vals = {
            display_name: name,
            parent_id: this.props.record.resId,
            user_ids: this.props.record.data.user_ids.resIds,
        };
        if (projectId) {
            vals.project_id = projectId;
        }
        await this.orm.create("project.task", [vals]);
        this.subtaskCreate.open = false;
        this.subtaskCreate.name = "";
        this.props.record.load();
    },
});
