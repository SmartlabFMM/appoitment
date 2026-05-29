# -*- coding: utf-8 -*-
"""
Contrôleur Portail — Interface web pour les patients.

Routes :
  GET  /clinic/request           → Formulaire de demande
  POST /clinic/request/submit    → Soumission de la demande
  GET  /clinic/my-requests       → Historique des demandes du patient
  GET  /clinic/request/<int:id>  → Détail d'une demande
"""
import base64
import logging

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

ALLOWED_MIMETYPES = {
    # Images
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp',
    # PDF
    'application/pdf',
    # DICOM
    'application/dicom', 'application/octet-stream',
    # Archives
    'application/zip',
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 Mo par fichier
MAX_FILES = 10


class ClinicPortalController(http.Controller):

    # ──────────────────────────────────────────────────────────────
    # Formulaire de demande
    # ──────────────────────────────────────────────────────────────

    @http.route('/clinic/request', type='http', auth='user', website=True)
    def appointment_request_form(self, **kwargs):
        """Affiche le formulaire de demande de rendez-vous."""
        patient = self._get_current_patient()
        specialities = request.env['medical.speciality'].sudo().search(
            [('active', '=', True)], order='name'
        )
        return request.render('clinic_appointment.portal_request_form', {
            'patient': patient,
            'specialities': specialities,
            'today': fields.Date.today(),
            'error': kwargs.get('error'),
            'success': kwargs.get('success'),
        })

    @http.route('/clinic/request/submit', type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def appointment_request_submit(self, **post):
        """Traite la soumission du formulaire."""
        patient = self._get_current_patient()
        if not patient:
            return request.redirect('/web/login')

        # Validation des champs obligatoires
        errors = []
        required = ['speciality_id', 'reason', 'preferred_date_from',
                    'appointment_type']
        for field in required:
            if not post.get(field):
                errors.append(f"Le champ '{field}' est obligatoire.")

        if errors:
            return request.render('clinic_appointment.portal_request_form', {
                'patient': patient,
                'specialities': request.env['medical.speciality'].sudo().search(
                    [('active', '=', True)]
                ),
                'today': fields.Date.today(),
                'errors': errors,
                'values': post,
            })

        try:
            # Créer la demande
            vals = {
                'patient_id': patient.id,
                'speciality_id': int(post['speciality_id']),
                'reason': post['reason'],
                'symptoms': post.get('symptoms', ''),
                'appointment_type': post['appointment_type'],
                'priority': post.get('priority', '0'),
                'preferred_date_from': post['preferred_date_from'],
                'preferred_date_to': post.get('preferred_date_to') or False,
                'preferred_morning': bool(post.get('preferred_morning')),
                'preferred_afternoon': bool(post.get('preferred_afternoon')),
            }

            preferred_doctor = post.get('preferred_doctor_id')
            if preferred_doctor and preferred_doctor.isdigit():
                vals['preferred_doctor_id'] = int(preferred_doctor)

            req = request.env['appointment.request'].sudo().create(vals)

            # Traiter les pièces jointes
            attachments = request.httprequest.files.getlist('attachments')
            attachment_ids = []
            for uploaded_file in attachments:
                if not uploaded_file.filename:
                    continue
                content = uploaded_file.read()
                if len(content) > MAX_FILE_SIZE:
                    _logger.warning(
                        "Fichier trop volumineux ignoré : %s (%d octets)",
                        uploaded_file.filename, len(content)
                    )
                    continue
                if uploaded_file.mimetype not in ALLOWED_MIMETYPES and \
                        not uploaded_file.filename.lower().endswith('.dcm'):
                    _logger.warning(
                        "Type MIME non autorisé ignoré : %s", uploaded_file.mimetype
                    )
                    continue
                attachment = request.env['ir.attachment'].sudo().create({
                    'name': uploaded_file.filename,
                    'datas': base64.b64encode(content),
                    'mimetype': uploaded_file.mimetype,
                    'res_model': 'appointment.request',
                    'res_id': req.id,
                })
                attachment_ids.append(attachment.id)

            if attachment_ids:
                req.sudo().write({
                    'attachment_ids': [(6, 0, attachment_ids)]
                })

            return request.redirect(f'/clinic/request/{req.id}?success=1')

        except (ValidationError, ValueError) as e:
            return request.render('clinic_appointment.portal_request_form', {
                'patient': patient,
                'specialities': request.env['medical.speciality'].sudo().search(
                    [('active', '=', True)]
                ),
                'today': fields.Date.today(),
                'errors': [str(e)],
                'values': post,
            })

    # ──────────────────────────────────────────────────────────────
    # Historique patient
    # ──────────────────────────────────────────────────────────────

    @http.route('/clinic/my-requests', type='http', auth='user', website=True)
    def my_requests(self, **kwargs):
        """Liste des demandes du patient connecté."""
        patient = self._get_current_patient()
        if not patient:
            return request.redirect('/clinic/register')

        requests_list = request.env['appointment.request'].sudo().search(
            [('patient_id', '=', patient.id)],
            order='create_date desc',
        )
        return request.render('clinic_appointment.portal_my_requests', {
            'patient': patient,
            'requests': requests_list,
        })

    @http.route('/clinic/request/<int:request_id>', type='http', auth='user', website=True)
    def request_detail(self, request_id, **kwargs):
        """Détail d'une demande."""
        patient = self._get_current_patient()
        req = request.env['appointment.request'].sudo().browse(request_id)

        if not req.exists() or req.patient_id.id != patient.id:
            return request.not_found()

        return request.render('clinic_appointment.portal_request_detail', {
            'patient': patient,
            'req': req,
            'success': kwargs.get('success'),
        })

    # ──────────────────────────────────────────────────────────────
    # API JSON pour le widget de sélection de créneaux
    # ──────────────────────────────────────────────────────────────

    @http.route('/clinic/api/doctors', type='json', auth='user')
    def api_get_doctors(self, speciality_id):
        """Retourne les médecins d'une spécialité (pour le formulaire dynamique)."""
        doctors = request.env['medical.doctor'].sudo().search([
            ('speciality_id', '=', int(speciality_id)),
            ('active', '=', True),
        ])
        return [{'id': d.id, 'name': d.display_name_full} for d in doctors]

    # ──────────────────────────────────────────────────────────────
    # Inscription patient
    # ──────────────────────────────────────────────────────────────

    @http.route('/clinic/register', type='http', auth='public', website=True)
    def patient_register_form(self, **kwargs):
        """Formulaire d'inscription d'un nouveau patient."""
        return request.render('clinic_appointment.portal_patient_register', {
            'today': fields.Date.today(),
            'error': kwargs.get('error'),
        })

    @http.route('/clinic/register/submit', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def patient_register_submit(self, **post):
        """Crée un compte patient + utilisateur portail."""
        errors = []
        for f in ['name', 'phone', 'email', 'password']:
            if not post.get(f):
                errors.append(f"Le champ '{f}' est obligatoire.")

        if errors:
            return request.render('clinic_appointment.portal_patient_register', {
                'errors': errors, 'values': post
            })

        # Vérifier unicité email
        existing_user = request.env['res.users'].sudo().search(
            [('login', '=', post['email'])], limit=1
        )
        if existing_user:
            return request.render('clinic_appointment.portal_patient_register', {
                'errors': ["Un compte avec cet email existe déjà."],
                'values': post,
            })

        try:
            # Créer l'utilisateur portail
            user = request.env['res.users'].sudo().create({
                'name': post['name'],
                'login': post['email'],
                'email': post['email'],
                'password': post['password'],
                'groups_id': [(6, 0, [
                    request.env.ref('base.group_portal').id,
                    request.env.ref(
                        'clinic_appointment.group_clinic_patient',
                        raise_if_not_found=False
                    ).id if request.env.ref(
                        'clinic_appointment.group_clinic_patient',
                        raise_if_not_found=False
                    ) else None,
                ])],
            })

            # Créer le dossier patient
            patient_vals = {
                'name': post['name'],
                'phone': post['phone'],
                'email': post['email'],
                'user_id': user.id,
            }
            if post.get('birth_date'):
                patient_vals['birth_date'] = post['birth_date']
            if post.get('gender'):
                patient_vals['gender'] = post['gender']

            request.env['medical.patient'].sudo().create(patient_vals)

            return request.redirect('/web/login?message=Compte créé avec succès. Connectez-vous.')

        except Exception as e:
            _logger.exception("Erreur création patient portail : %s", e)
            return request.render('clinic_appointment.portal_patient_register', {
                'errors': [str(e)], 'values': post
            })

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────

    def _get_current_patient(self):
        """Retourne le dossier patient de l'utilisateur connecté, ou None."""
        if request.env.user._is_public():
            return None
        patient = request.env['medical.patient'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1
        )
        return patient or None
