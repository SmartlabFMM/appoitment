# -*- coding: utf-8 -*-
"""
Cron job intelligent pour la gestion automatique des absences et
le décalage des rendez-vous suivants avec notification Telegram.

Logique complète :
  1. Toutes les 5 min : cherche les RDV confirmés dont l'heure est
     dépassée de N minutes (config) sans pointage (état != waiting/in_progress)
  2. Marque ces RDV comme 'no_show'
  3. Décale automatiquement tous les RDV suivants du même médecin/date
     en avançant chacun d'un slot (durée consultation)
  4. Envoie une notification Telegram à chaque patient affecté
  5. Poste un résumé dans le chatter de chaque RDV modifié

Ce fichier s'ajoute dans models/ et s'importe dans models/__init__.py
"""
import logging
from datetime import datetime, timedelta, date as date_type

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class MedicalAppointmentCron(models.Model):
    """
    Extension du modèle medical.appointment pour les méthodes cron.
    Hérite du modèle existant sans créer de nouvelle table.
    """
    _inherit = 'medical.appointment'

    # ── Champs supplémentaires pour le tracking du décalage ──────────────────

    shifted_count = fields.Integer(
        string='Fois décalé',
        default=0,
        help='Nombre de fois que ce RDV a été décalé automatiquement.',
    )
    original_time = fields.Float(
        string='Heure originale',
        help='Heure de RDV originale avant tout décalage automatique.',
        copy=True,
    )

    # ── Méthode principale du cron ────────────────────────────────────────────

    @api.model
    def _cron_handle_no_shows_and_shift(self):
        """
        Méthode appelée par le cron toutes les 5 minutes.
        Orchestre : détection absences → marquage → décalage → notification.
        """
        _logger.info('=== CRON no-show & shift : démarrage ===')

        # Lire la config du délai (défaut 30 min)
        delay_minutes = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'clinic.telegram_no_show_delay', '30'
            )
        )

        now       = datetime.now()
        today     = fields.Date.today()
        cutoff_dt = now - timedelta(minutes=delay_minutes)

        # ── Étape 1 : Trouver les RDV confirmés qui auraient dû être pointés ──
        # Un RDV est "en retard" si :
        #   - état = confirmed (pas encore waiting/in_progress/done)
        #   - date = aujourd'hui
        #   - son heure de début + délai < maintenant
        confirmed_today = self.search([
            ('appointment_date', '=', today),
            ('state', '=', 'confirmed'),
        ])

        no_show_appointments = self.browse()
        for appt in confirmed_today:
            if not appt.appointment_datetime:
                continue
            # appointment_datetime est stocké en UTC, on compare avec now() UTC
            appt_dt = appt.appointment_datetime
            if appt_dt + timedelta(minutes=delay_minutes) <= now:
                no_show_appointments |= appt

        if not no_show_appointments:
            _logger.info('CRON: aucun no-show détecté.')
            return

        _logger.info('CRON: %d no-show(s) détecté(s).', len(no_show_appointments))

        # ── Étape 2 : Pour chaque no-show, marquer + décaler les suivants ─────
        # Grouper par médecin pour traiter les décalages en bloc
        doctors_affected = no_show_appointments.mapped('doctor_id')

        for doctor in doctors_affected:
            doctor_no_shows = no_show_appointments.filtered(
                lambda a: a.doctor_id == doctor
            )
            self._process_doctor_no_shows(doctor, doctor_no_shows, today, delay_minutes)

        _logger.info('=== CRON no-show & shift : terminé ===')

    # ── Traitement par médecin ────────────────────────────────────────────────

    @api.model
    def _process_doctor_no_shows(self, doctor, no_show_appts, today, delay_minutes):
        """
        Pour un médecin donné :
        1. Marque les no-shows
        2. Récupère tous les RDV suivants de la journée
        3. Décale chaque RDV du nombre de slots manqués
        4. Notifie les patients via Telegram
        """
        telegram = self.env['clinic.telegram.service']
        duration_h = (doctor.consultation_duration or 30) / 60.0

        # Trier les no-shows par heure croissante
        sorted_no_shows = no_show_appts.sorted('appointment_time')

        for appt in sorted_no_shows:
            _logger.info('CRON: marquage no-show RDV %s (%s)', appt.name, appt.patient_id.name)

            # Sauvegarder l'heure originale si c'est la première fois
            if not appt.original_time:
                appt.original_time = appt.appointment_time

            appt.write({'state': 'no_show'})
            appt.message_post(
                body=(
                    f"⏰ <b>Absent automatiquement détecté</b><br/>"
                    f"Le patient n'a pas été pointé {delay_minutes} minutes après l'heure du RDV.<br/>"
                    f"Statut passé à <b>Absent</b> automatiquement par le système."
                ),
                message_type='notification',
            )

            # Notifier le patient no-show via Telegram
            telegram.notify_no_show_marked(appt)

        # ── Étape 3 : Décaler les RDV suivants ───────────────────────────────
        # Récupérer tous les RDV confirmed/waiting après le dernier no-show
        last_no_show_time = max(a.appointment_time for a in sorted_no_shows)

        next_appointments = self.search([
            ('doctor_id',        '=', doctor.id),
            ('appointment_date', '=', today),
            ('appointment_time', '>',  last_no_show_time),
            ('state',            'in', ['confirmed', 'waiting', 'draft']),
        ], order='appointment_time asc')

        if not next_appointments:
            _logger.info('CRON: aucun RDV à décaler pour Dr %s.', doctor.name)
            return

        # Calculer le décalage : nombre de no-shows × durée consultation
        shift_hours = len(sorted_no_shows) * duration_h
        _logger.info(
            'CRON: décalage de %d RDV de %.2f h pour Dr %s.',
            len(next_appointments), shift_hours, doctor.name,
        )

        for appt in next_appointments:
            old_time     = appt.appointment_time
            old_time_str = appt.appointment_time_display or _fmt_time(old_time)
            new_time     = old_time - shift_hours  # avancer = réduire l'heure

            # Vérifier qu'on ne recule pas avant le début de journée
            if new_time < 0:
                _logger.warning('CRON: impossible de décaler %s en dehors des heures.', appt.name)
                continue

            new_time_str = _fmt_time(new_time)

            # Sauvegarder l'heure originale si première fois
            if not appt.original_time:
                appt.original_time = old_time

            appt.write({
                'appointment_time': new_time,
                'shifted_count':    appt.shifted_count + 1,
            })

            appt.message_post(
                body=(
                    f"⏩ <b>Rendez-vous avancé automatiquement</b><br/>"
                    f"Ancien créneau : <b>{old_time_str}</b><br/>"
                    f"Nouveau créneau : <b>{new_time_str}</b><br/>"
                    f"Raison : absence détectée d'un patient précédent."
                ),
                message_type='notification',
            )

            # Notifier le patient via Telegram
            telegram.notify_appointment_shifted(
                appt,
                new_time_str,
                reason="Un patient précédent ne s'est pas présenté.",
            )

            _logger.info(
                'CRON: RDV %s décalé %s → %s (patient: %s)',
                appt.name, old_time_str, new_time_str, appt.patient_id.name,
            )

    # ── Override action_confirm pour notifier via Telegram ───────────────────

    def action_confirm(self):
        """Override pour envoyer une notification Telegram à la confirmation."""
        res = super().action_confirm()
        telegram = self.env['clinic.telegram.service']
        for rec in self.filtered(lambda a: a.state == 'confirmed'):
            telegram.notify_appointment_confirmed(rec)
        return res


# ── Helper ────────────────────────────────────────────────────────────────────

def _fmt_time(value: float) -> str:
    h = int(value)
    m = round((value - h) * 60)
    return f'{h:02d}:{m:02d}'
