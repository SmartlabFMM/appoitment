/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";

/**
 * Composant Tableau de Bord Clinique
 */
class ClinicDashboard extends Component {
    static template = "clinic_appointment.Dashboard";

    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.state = useState({
            stats: {
                today_total: 0,
                today_confirmed: 0,
                today_done: 0,
                today_waiting: 0,
                month_total: 0,
                urgent_pending: 0,
            },
            loading: true,
        });

        onMounted(() => this.loadStats());
    }

    async loadStats() {
        try {
            const stats = await this.rpc("/web/dataset/call_kw", {
                model: "medical.appointment",
                method: "get_dashboard_stats",
                args: [],
                kwargs: {},
            });
            this.state.stats = stats;
        } catch (e) {
            console.error("Erreur chargement stats:", e);
        } finally {
            this.state.loading = false;
        }
    }

    openTodayAppointments() {
        this.action.doAction("clinic_appointment.action_appointment_today");
    }

    openAllAppointments() {
        this.action.doAction("clinic_appointment.action_medical_appointment");
    }

    openUrgentAppointments() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Rendez-Vous Urgents",
            res_model: "medical.appointment",
            view_mode: "list,form",
            domain: [["priority", "in", ["1", "2"]], ["state", "not in", ["done", "cancelled"]]],
        });
    }
}

// Enregistrement dans la registry des actions client
registry.category("actions").add("clinic_dashboard", ClinicDashboard);

// ─── Utilitaires JS ───────────────────────────────────────────────

/**
 * Formater une durée float en HH:MM
 */
function formatFloatTime(value) {
    const hours = Math.floor(value);
    const minutes = Math.round((value - hours) * 60);
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

/**
 * Calculer créneaux disponibles côté client
 */
function computeAvailableSlots(schedules, bookedTimes, duration) {
    const slots = [];
    for (const schedule of schedules) {
        let current = schedule.start_time;
        while (current + duration / 60 <= schedule.end_time) {
            const timeStr = formatFloatTime(current);
            if (!bookedTimes.includes(current)) {
                slots.push({ value: current, label: timeStr });
            }
            current += duration / 60;
        }
    }
    return slots;
}

export { ClinicDashboard, formatFloatTime, computeAvailableSlots };
