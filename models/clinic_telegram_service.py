# -*- coding: utf-8 -*-
"""
Service Telegram centralisé pour le module clinic_appointment.
Toutes les fonctions d'envoi passent par ce service.
"""
import requests
import logging

from odoo import models, api

_logger = logging.getLogger(__name__)

TELEGRAM_API = 'https://api.telegram.org/bot{token}/{method}'


class ClinicTelegramService(models.AbstractModel):
    """
    Service abstrait — pas de table en base.
    Utilisé via : self.env['clinic.telegram.service'].send_message(...)
    """
    _name        = 'clinic.telegram.service'
    _description = 'Service Telegram Clinique'

    # ── Config helpers ────────────────────────────────────────────────────────

    def _get_token(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'clinic.telegram_bot_token', ''
        )

    def _is_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'clinic.telegram_notifications_enabled', 'False'
        ) == 'True'

    # ── Core send ────────────────────────────────────────────────────────────

    @api.model
    def send_message(self, chat_id: str, text: str, parse_mode: str = 'HTML') -> bool:
        """
        Envoie un message Telegram à un chat_id donné.
        Retourne True si succès, False sinon (sans lever d'exception).
        """
        if not self._is_enabled():
            _logger.debug('Telegram désactivé — message non envoyé.')
            return False

        token = self._get_token()
        if not token or not chat_id:
            _logger.warning('Telegram: token ou chat_id manquant.')
            return False

        try:
            url  = TELEGRAM_API.format(token=token, method='sendMessage')
            resp = requests.post(url, json={
                'chat_id':    chat_id,
                'text':       text,
                'parse_mode': parse_mode,
            }, timeout=10)
            data = resp.json()
            if data.get('ok'):
                _logger.info('Telegram: message envoyé à %s', chat_id)
                return True
            else:
                _logger.warning('Telegram: erreur API — %s', data.get('description'))
                return False
        except Exception as e:
            _logger.error('Telegram: exception — %s', str(e))
            return False

    # ── Message templates ─────────────────────────────────────────────────────

    @api.model
    def notify_appointment_shifted(self, appointment, new_time_str: str, reason: str):
        """Notifie un patient que son RDV a été avancé."""
        patient = appointment.patient_id
        if not patient.telegram_notifications or not patient.telegram_chat_id:
            return False

        doctor_name = appointment.doctor_id.display_name_full or appointment.doctor_id.name
        old_time    = appointment.appointment_time_display or '?'
        date_str    = str(appointment.appointment_date)

        text = (
            f"🏥 <b>ClinicPlus — Mise à jour de votre rendez-vous</b>\n\n"
            f"Bonjour <b>{patient.name}</b>,\n\n"
            f"Votre rendez-vous a été <b>avancé automatiquement</b> :\n\n"
            f"👨‍⚕️ Médecin : <b>{doctor_name}</b>\n"
            f"📅 Date : <b>{date_str}</b>\n"
            f"🕐 Ancien créneau : <b>{old_time}</b>\n"
            f"🕐 Nouveau créneau : <b>{new_time_str}</b>\n\n"
            f"ℹ️ Raison : {reason}\n\n"
            f"Merci de vous présenter <b>15 minutes avant</b> l'heure prévue.\n"
            f"Pour toute question, contactez la clinique."
        )
        return self.send_message(patient.telegram_chat_id, text)

    @api.model
    def notify_no_show_marked(self, appointment):
        """Notifie un patient qu'il a été marqué absent."""
        patient = appointment.patient_id
        if not patient.telegram_notifications or not patient.telegram_chat_id:
            return False

        doctor_name = appointment.doctor_id.display_name_full or appointment.doctor_id.name
        text = (
            f"🏥 <b>ClinicPlus — Rendez-vous manqué</b>\n\n"
            f"Bonjour <b>{patient.name}</b>,\n\n"
            f"Vous avez été marqué(e) <b>absent(e)</b> pour votre rendez-vous :\n\n"
            f"👨‍⚕️ Médecin : <b>{doctor_name}</b>\n"
            f"📅 Date : <b>{appointment.appointment_date}</b>\n"
            f"🕐 Heure : <b>{appointment.appointment_time_display}</b>\n\n"
            f"Si c'est une erreur, contactez la clinique rapidement.\n"
            f"Vous pouvez reprendre un rendez-vous via notre application."
        )
        return self.send_message(patient.telegram_chat_id, text)

    @api.model
    def notify_appointment_confirmed(self, appointment):
        """Notifie un patient que son RDV est confirmé."""
        patient = appointment.patient_id
        if not patient.telegram_notifications or not patient.telegram_chat_id:
            return False

        doctor_name = appointment.doctor_id.display_name_full or appointment.doctor_id.name
        text = (
            f"🏥 <b>ClinicPlus — Rendez-vous confirmé ✅</b>\n\n"
            f"Bonjour <b>{patient.name}</b>,\n\n"
            f"Votre rendez-vous est <b>confirmé</b> :\n\n"
            f"👨‍⚕️ Médecin : <b>{doctor_name}</b>\n"
            f"📅 Date : <b>{appointment.appointment_date}</b>\n"
            f"🕐 Heure : <b>{appointment.appointment_time_display}</b>\n"
            f"⏱ Durée : <b>{appointment.duration or 30} min</b>\n\n"
            f"Merci de vous présenter <b>15 minutes avant</b> l'heure prévue. 🙏"
        )
        return self.send_message(patient.telegram_chat_id, text)
