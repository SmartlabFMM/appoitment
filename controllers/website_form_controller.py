# -*- coding: utf-8 -*-
"""
Website Form Controller — Version simplifiée
Le patient soumet uniquement ses infos + spécialité + motif + disponibilités.
Aucun choix de médecin, date ou heure.
Crée : medical.patient (si nouveau) + appointment.request (état 'new')
La secrétaire traite ensuite la demande via le backend.
"""
import logging
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class WebsiteAppointmentForm(http.Controller):

    # ── 1. Afficher le formulaire ─────────────────────────────────
    @http.route('/appointment/new', type='http', auth='public', website=True)
    def appointment_form(self, **kwargs):
        specialities = request.env['medical.speciality'].sudo().search(
            [('active', '=', True)], order='name'
        )
        return request.render(
            'clinic_appointment_extension.website_appointment_form',
            {
                'specialities': specialities,
                'today': str(fields.Date.today()),
                'errors': [],
                'values': {},
            }
        )

    # ── 2. Traiter la soumission ──────────────────────────────────
    @http.route('/appointment/submit', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    def appointment_submit(self, **post):
        errors = _validate(post)

        if errors:
            specialities = request.env['medical.speciality'].sudo().search(
                [('active', '=', True)], order='name'
            )
            return request.render(
                'clinic_appointment_extension.website_appointment_form',
                {
                    'specialities': specialities,
                    'today': str(fields.Date.today()),
                    'errors': errors,
                    'values': post,
                }
            )

        try:
            Patient = request.env['medical.patient'].sudo()
            AppRequest = request.env['appointment.request'].sudo()

            # ── Étape 1 : trouver ou créer le patient ─────────────
            cin = post.get('cin', '').strip()
            patient = None

            # Priorité 1 : recherche par CIN
            if cin:
                patient = Patient.search([('cin', '=', cin)], limit=1)
                if patient:
                    _logger.info(
                        "Patient trouvé par CIN %s : %s (id=%s)",
                        cin, patient.name, patient.id
                    )

            # Priorité 2 : recherche par téléphone si CIN non trouvé
            if not patient:
                patient = Patient.search([('phone', '=', post['phone'])], limit=1)
                if patient:
                    _logger.info(
                        "Patient trouvé par téléphone %s : %s (id=%s)",
                        post['phone'], patient.name, patient.id
                    )
                    # Mettre à jour le CIN s'il manquait
                    if cin and not patient.cin:
                        patient.write({'cin': cin})

            # Priorité 3 : créer un nouveau patient
            if not patient:
                patient_vals = {
                    'name': post['patient_name'],
                    'phone': post['phone'],
                    'email': post.get('email', ''),
                }
                if cin:
                    patient_vals['cin'] = cin
                if post.get('birth_date'):
                    patient_vals['birth_date'] = post['birth_date']
                if post.get('gender'):
                    patient_vals['gender'] = post['gender']
                patient = Patient.create(patient_vals)
                _logger.info(
                    "Nouveau patient créé : %s (id=%s)", patient.name, patient.id
                )

            # ── Étape 2 : créer la demande de rendez-vous ─────────
            request_vals = {
                'patient_id': patient.id,
                'speciality_id': int(post['speciality_id']),
                'reason': post['reason'],
                'appointment_type': post.get('appointment_type', 'first'),
                'priority': post.get('priority', '0'),
                'preferred_date_from': post.get('preferred_date_from') or fields.Date.today(),
                'preferred_morning': bool(post.get('preferred_morning')),
                'preferred_afternoon': bool(post.get('preferred_afternoon')),
            }
            if post.get('preferred_date_to'):
                request_vals['preferred_date_to'] = post['preferred_date_to']
            if post.get('symptoms'):
                request_vals['symptoms'] = post['symptoms']

            appt_request = AppRequest.create(request_vals)
            _logger.info(
                "Demande créée : %s pour patient %s", appt_request.name, patient.name
            )

            # ── Étape 3 : traiter les pièces jointes ──────────────
            import base64
            uploaded_files = request.httprequest.files.getlist('attachments')
            attachment_ids = []
            ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.dcm', '.zip'}
            MAX_SIZE = 20 * 1024 * 1024  # 20 Mo

            for f in uploaded_files:
                if not f.filename:
                    continue
                ext = '.' + f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
                content = f.read()
                if ext not in ALLOWED_EXT:
                    _logger.warning("Fichier ignoré (type non autorisé) : %s", f.filename)
                    continue
                if len(content) > MAX_SIZE:
                    _logger.warning("Fichier ignoré (trop volumineux) : %s", f.filename)
                    continue
                att = request.env['ir.attachment'].sudo().create({
                    'name': f.filename,
                    'datas': base64.b64encode(content),
                    'mimetype': f.mimetype or 'application/octet-stream',
                    'res_model': 'appointment.request',
                    'res_id': appt_request.id,
                })
                attachment_ids.append(att.id)

            if attachment_ids:
                appt_request.sudo().write({
                    'attachment_ids': [(6, 0, attachment_ids)]
                })
                _logger.info("%d fichier(s) attaché(s) à la demande %s",
                             len(attachment_ids), appt_request.name)

            return request.redirect(f'/appointment/confirmation/{appt_request.id}')

        except Exception as e:
            _logger.exception("Erreur création demande : %s", e)
            specialities = request.env['medical.speciality'].sudo().search(
                [('active', '=', True)], order='name'
            )
            return request.render(
                'clinic_appointment_extension.website_appointment_form',
                {
                    'specialities': specialities,
                    'today': str(fields.Date.today()),
                    'errors': [f'Erreur serveur : {str(e)}'],
                    'values': post,
                }
            )

    # ── 3. Page de confirmation ───────────────────────────────────
    @http.route('/appointment/confirmation/<int:req_id>',
                type='http', auth='public', website=True)
    def appointment_confirmation(self, req_id, **kwargs):
        appt_request = request.env['appointment.request'].sudo().browse(req_id)
        if not appt_request.exists():
            return request.not_found()
        return request.render(
            'clinic_appointment_extension.website_appointment_confirmation',
            {'appt_request': appt_request}
        )


# ── Validation ────────────────────────────────────────────────────

def _validate(post):
    errors = []
    required = {
        'cin': 'CIN',
        'patient_name': 'Nom complet',
        'phone': 'Téléphone',
        'speciality_id': 'Spécialité médicale',
        'reason': 'Motif de la consultation',
    }
    for field, label in required.items():
        if not post.get(field):
            errors.append(f'Le champ « {label} » est obligatoire.')
    # Valider format CIN : 8 chiffres
    cin = post.get('cin', '').strip()
    if cin and (not cin.isdigit() or len(cin) != 8):
        errors.append('Le CIN doit contenir exactement 8 chiffres.')
    return errors