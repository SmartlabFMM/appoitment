# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, time
import logging
import secrets
import string

_logger = logging.getLogger(__name__)


class MedicalDoctor(models.Model):
    _name = 'medical.doctor'
    _description = 'Médecin'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    # Informations personnelles
    name = fields.Char(
        string='Nom Complet',
        required=True,
        tracking=True,
    )
    ref = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
    )
    gender = fields.Selection([
        ('male', 'Homme'),
        ('female', 'Femme'),
    ], string='Genre', default='male', tracking=True)

    title = fields.Selection([
        ('dr', 'Dr.'),
        ('pr', 'Pr.'),
    ], string='Titre', default='dr')

    display_name_full = fields.Char(
        string='Nom Affiché',
        compute='_compute_display_name_full',
        store=True,
    )

    phone = fields.Char(string='Téléphone', tracking=True)
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Email', tracking=True)
    image = fields.Binary(string='Photo', attachment=True)
    birth_date = fields.Date(string='Date de Naissance')
    address = fields.Text(string='Adresse')

    # Informations professionnelles
    speciality_id = fields.Many2one(
        'medical.speciality',
        string='Spécialité',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    license_number = fields.Char(
        string='Numéro de Licence',
        tracking=True,
    )
    experience_years = fields.Integer(
        string='Années d\'Expérience',
        default=0,
    )
    consultation_fee = fields.Float(
        string='Honoraires de Consultation (DT)',
        digits=(10, 3),
    )
    # consultation_duration = fields.Integer(
    #     string='Durée de Consultation (min)',
    #     default=30,
    #     help='Durée par défaut d\'une consultation pour ce médecin',
    # )

    # Lien utilisateur
    user_id = fields.Many2one(
        'res.users',
        string='Compte Utilisateur',
        tracking=True,
        domain="[('share', '=', False)]",
    )

    active = fields.Boolean(string='Actif', default=True, tracking=True)
    notes = fields.Text(string='Notes')

    # Disponibilités
    schedule_ids = fields.One2many(
        'medical.schedule',
        'doctor_id',
        string='Plannings',
    )

    # Rendez-vous
    appointment_ids = fields.One2many(
        'medical.appointment',
        'doctor_id',
        string='Rendez-Vous',
    )
    appointment_count = fields.Integer(
        string='Total Rendez-Vous',
        compute='_compute_appointment_count',
    )
    today_appointment_count = fields.Integer(
        string='Rendez-Vous Aujourd\'hui',
        compute='_compute_today_appointment_count',
    )

    # ------------------------------------------------
    # Computed
    consultation_duration = fields.Integer(
        related='speciality_id.average_duration',
        string='Durée de Consultation (min)',
        default=30,
        help='Durée par défaut d\'une consultation pour ce médecin',
    )
    # ------------------------------------------------

    @api.depends('title', 'name')
    def _compute_display_name_full(self):
        for rec in self:
            prefix = dict(self._fields['title'].selection).get(rec.title, '')
            rec.display_name_full = f"{prefix} {rec.name}" if prefix else rec.name

    def _compute_appointment_count(self):
        for rec in self:
            rec.appointment_count = self.env['medical.appointment'].search_count([
                ('doctor_id', '=', rec.id),
                ('state', 'not in', ['cancelled']),
            ])

    def _compute_today_appointment_count(self):
        today = fields.Date.today()
        for rec in self:
            rec.today_appointment_count = self.env['medical.appointment'].search_count([
                ('doctor_id', '=', rec.id),
                ('appointment_date', '=', today),
                ('state', 'not in', ['cancelled']),
            ])

    # ------------------------------------------------
    # ORM
    # ------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref', 'Nouveau') == 'Nouveau':
                vals['ref'] = self.env['ir.sequence'].next_by_code('medical.doctor') or 'Nouveau'
        doctors = super().create(vals_list)
        # print(doctors)
        # Créer automatiquement un utilisateur Odoo pour chaque médecin
        for doctor in doctors:
            if not doctor.user_id:
                doctor._create_doctor_user()
        return doctors

    # ------------------------------------------------
    # Création automatique de l'utilisateur
    # ------------------------------------------------

    def _generate_login(self, name, email=None):
        """Génère un login unique pour le médecin."""
        if email:
            base_login = email.lower().strip()
        else:
            # Construire un login à partir du nom : "Dr Ahmed Ben Ali" → "ahmed.benali"
            parts = name.lower().strip().split()
            # Ignorer les titres éventuels
            ignore = {'dr.', 'pr.', 'dr', 'pr'}
            parts = [p for p in parts if p not in ignore]
            base_login = '.'.join(parts) if parts else 'medecin'

        # S'assurer de l'unicité
        login = base_login
        counter = 1
        while self.env['res.users'].sudo().search_count([('login', '=', login)]):
            login = f"{base_login}{counter}"
            counter += 1
        return login

    def _generate_temp_password(self, length=12):
        """Génère un mot de passe temporaire sécurisé."""
        alphabet = string.ascii_letters + string.digits + '!@#$%'
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _create_doctor_user(self):
        """
        Crée un utilisateur Odoo lié à ce médecin et lui attribue
        le groupe 'Clinic / Médecin' pour qu'il accède à son planning
        et ses rendez-vous uniquement.
        """
        self.ensure_one()

        # Récupérer le groupe médecin
        group_doctor = self.env.ref(
            'clinic_appointment.group_clinic_doctor',
            raise_if_not_found=False,
        )
        # Récupérer le groupe de base (Utilisateur interne)
        group_internal = self.env.ref('base.group_user', raise_if_not_found=False)

        login = self._generate_login(self.name, self.email)
        temp_password = self._generate_temp_password()
        # print(login)
        # print(temp_password)

        user_vals = {
            'name': self.display_name_full or self.name,
            'login': login,
            'email': self.email or False,
            'image_1920': self.image or False,
            'phone': self.phone or False,
            'active': True,
            'share': False,  # Utilisateur interne
            'group_ids': [],
        }

        # Construire la liste des groupes
        groups = []
        if group_internal:
            groups.append((4, group_internal.id))
        if group_doctor:
            groups.append((4, group_doctor.id))
        if groups:
            user_vals['group_ids'] = groups

        try:
            user = self.env['res.users'].sudo().with_context(
                no_reset_password=True
            ).create(user_vals)
            print(user)

            # Définir le mot de passe temporaire
            user.sudo()._set_encrypted_password(
                user.id,
                self.env['res.users']._crypt_context().hash(temp_password)
            )

            # Lier l'utilisateur au médecin
            self.sudo().write({'user_id': user.id})

            _logger.info(
                "Utilisateur créé pour le médecin %s : login=%s",
                self.name, login,
            )

            # Notifier dans le chatter avec les identifiants temporaires
            html_body = Markup(
                f"<p>✅ <strong>Compte utilisateur créé automatiquement</strong></p>"
                    f"<ul>"
                    f"<li><strong>Login :</strong> {login}</li>"
                    f"<li><strong>Mot de passe temporaire :</strong> {temp_password}</li>"
                    f"</ul>"
                    f"<p>⚠️ Veuillez communiquer ces identifiants au médecin et lui demander "
                    f"de changer son mot de passe dès la première connexion.</p>"
            )
            self.message_post(
                body=html_body,
                subject="Compte utilisateur créé",
                message_type='notification',
            )
            mail_values = {
                'subject': f'Votre compte est créé!',
                'body_html': f"""
                                <p>Bonjour <strong>{self.name}</strong>,</p>
                                <p>Votre compte utilisateur (Médecin) est créé :</p>
                                <ul>
                                    <li><strong>Login :</strong> {login}</li>
                                    <li><strong>Mot de passe temporaire :</strong> {temp_password}</li>
                                </ul>
                                <p>Merci de changer votre mot de passe dès la première connexion.</p>
                                """,
                'email_to': self.email,
                'email_from': 'arafettekaya@gmail.com',
            }
            self.env['mail.mail'].create(mail_values).send()

        except Exception as e:
            _logger.error(
                "Erreur lors de la création de l'utilisateur pour le médecin %s : %s",
                self.name, str(e),
            )
            # Ne pas bloquer la création du médecin
            self.message_post(
                body=(
                    f"<p>⚠️ <strong>Impossible de créer le compte utilisateur automatiquement.</strong></p>"
                    f"<p>Erreur : {str(e)}</p>"
                    f"<p>Vous pouvez créer le compte manuellement via le champ "
                    f"<em>Compte Utilisateur</em>.</p>"
                ),
                message_type='notification',
            )

    # ------------------------------------------------
    # Action manuelle (bouton) : recréer / réinitialiser l'utilisateur
    # ------------------------------------------------

    def action_create_user(self):
        """
        Bouton dans la fiche médecin pour créer/recréer manuellement l'utilisateur.
        Utile si la création automatique a échoué.
        """
        for rec in self:
            if rec.user_id:
                raise ValidationError(
                    f"Ce médecin possède déjà un compte utilisateur : {rec.user_id.login}\n"
                    f"Archivez-le d'abord si vous souhaitez en créer un nouveau."
                )
            rec._create_doctor_user()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Succès',
                'message': 'Le compte utilisateur a été créé avec succès.',
                'type': 'success',
                'sticky': False,
            },
        }

    # ------------------------------------------------
    # Constraintes
    # ------------------------------------------------

    @api.constrains('consultation_duration')
    def _check_duration(self):
        for rec in self:
            if rec.consultation_duration <= 0:
                raise ValidationError("La durée de consultation doit être supérieure à 0.")

    # ------------------------------------------------
    # Actions de navigation
    # ------------------------------------------------

    def action_view_appointments(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Rendez-Vous de {self.display_name_full}',
            'res_model': 'medical.appointment',
            'view_mode': 'calendar,list,form',
            'domain': [('doctor_id', '=', self.id)],
            'context': {'default_doctor_id': self.id},
        }

    def action_view_schedule(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Planning de {self.display_name_full}',
            'res_model': 'medical.schedule',
            'view_mode': 'list,form',
            'domain': [('doctor_id', '=', self.id)],
            'context': {'default_doctor_id': self.id},
        }

    def get_available_slots(self, date):
        """Retourne les créneaux disponibles pour un médecin à une date donnée"""
        self.ensure_one()
        day_of_week = str(date.weekday())  # 0=lundi, 6=dimanche

        schedules = self.schedule_ids.filtered(
            lambda s: s.day_of_week == day_of_week and s.active
        )

        if not schedules:
            return []

        existing_appointments = self.env['medical.appointment'].search([
            ('doctor_id', '=', self.id),
            ('appointment_date', '=', date),
            ('state', 'not in', ['cancelled']),
        ])
        booked_times = [a.appointment_time for a in existing_appointments]

        available_slots = []
        for schedule in schedules:
            current_time = schedule.start_time
            while current_time + (self.consultation_duration / 60.0) <= schedule.end_time:
                if current_time not in booked_times:
                    available_slots.append(current_time)
                current_time += self.consultation_duration / 60.0

        return available_slots
