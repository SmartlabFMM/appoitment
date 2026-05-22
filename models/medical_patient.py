# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date


class MedicalPatient(models.Model):
    _name = 'medical.patient'
    _description = 'Patient'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    # Informations personnelles
    name = fields.Char(string='Nom Complet', required=True, tracking=True)
    ref  = fields.Char(string='Numéro Dossier', readonly=True, copy=False, default='Nouveau')

    gender = fields.Selection([('male', 'Homme'), ('female', 'Femme')], string='Genre', tracking=True)

    birth_date = fields.Date(string='Date de Naissance')
    age = fields.Integer(string='Âge', compute='_compute_age', store=False)

    phone  = fields.Char(string='Téléphone', required=True, tracking=True)
    email  = fields.Char(string='Email', tracking=True)
    address = fields.Text(string='Adresse')
    city    = fields.Char(string='Ville')

    governorate = fields.Selection([
        ('tunis', 'Tunis'), ('ariana', 'Ariana'), ('ben_arous', 'Ben Arous'),
        ('manouba', 'Manouba'), ('nabeul', 'Nabeul'), ('zaghouan', 'Zaghouan'),
        ('bizerte', 'Bizerte'), ('beja', 'Béja'), ('jendouba', 'Jendouba'),
        ('kef', 'Le Kef'), ('siliana', 'Siliana'), ('sousse', 'Sousse'),
        ('monastir', 'Monastir'), ('mahdia', 'Mahdia'), ('sfax', 'Sfax'),
        ('kairouan', 'Kairouan'), ('kasserine', 'Kasserine'), ('sidi_bouzid', 'Sidi Bouzid'),
        ('gabes', 'Gabès'), ('medenine', 'Médenine'), ('tataouine', 'Tataouine'),
        ('gafsa', 'Gafsa'), ('tozeur', 'Tozeur'), ('kebili', 'Kébili'),
    ], string='Gouvernorat')

    blood_group = fields.Selection([
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-'),
    ], string='Groupe Sanguin')

    # Informations médicales
    allergies          = fields.Text(string='Allergies')
    chronic_diseases   = fields.Text(string='Maladies Chroniques')
    current_medications = fields.Text(string='Médicaments en Cours')
    medical_history    = fields.Text(string='Antécédents Médicaux')

    # Assurance
    insurance_type = fields.Selection([
        ('cnss', 'CNSS'), ('cnrps', 'CNRPS'),
        ('private', 'Assurance Privée'), ('none', 'Aucune'),
    ], string="Type d'Assurance", default='none')
    insurance_number = fields.Char(string="Numéro d'Assurance")

    # Compte utilisateur
    user_id = fields.Many2one('res.users', string='Compte Utilisateur', tracking=True)

    image         = fields.Binary(string='Photo', attachment=True)
    active        = fields.Boolean(string='Actif', default=True, tracking=True)
    password_hash = fields.Char(string='Mot de Passe Web', copy=False, groups='base.group_system')
    notes         = fields.Text(string='Notes Complémentaires')

    # ── Telegram ─────────────────────────────────────────────────────────────
    telegram_chat_id = fields.Char(
        string='Telegram Chat ID',
        help=(
            'ID Telegram du patient pour recevoir les notifications automatiques. '
            'Le patient doit démarrer une conversation avec le bot et envoyer /start. '
            'L\'ID apparaîtra alors ici après synchronisation.'
        ),
        tracking=True,
        copy=False,
    )
    telegram_notifications = fields.Boolean(
        string='Notifications Telegram',
        default=False,
        help='Activer les notifications Telegram pour ce patient.',
    )

    # Rendez-vous
    appointment_ids = fields.One2many('medical.appointment', 'patient_id', string='Rendez-Vous')
    appointment_count = fields.Integer(string='Total Rendez-Vous', compute='_compute_appointment_count')
    last_appointment_date = fields.Date(
        string='Dernier Rendez-Vous',
        compute='_compute_last_appointment',
        store=True,
    )

    # ── Computed ─────────────────────────────────────────────────────────────

    @api.depends('birth_date')
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if rec.birth_date:
                rec.age = today.year - rec.birth_date.year - (
                    (today.month, today.day) < (rec.birth_date.month, rec.birth_date.day)
                )
            else:
                rec.age = 0

    def _compute_appointment_count(self):
        for rec in self:
            rec.appointment_count = self.env['medical.appointment'].search_count([
                ('patient_id', '=', rec.id),
            ])

    @api.depends('appointment_ids.appointment_date', 'appointment_ids.state')
    def _compute_last_appointment(self):
        for rec in self:
            last = self.env['medical.appointment'].search([
                ('patient_id', '=', rec.id),
                ('state', '=', 'done'),
            ], order='appointment_date desc', limit=1)
            rec.last_appointment_date = last.appointment_date if last else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref', 'Nouveau') == 'Nouveau':
                vals['ref'] = self.env['ir.sequence'].next_by_code('medical.patient') or 'Nouveau'
        return super().create(vals_list)

    def action_view_appointments(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Rendez-Vous de {self.name}',
            'res_model': 'medical.appointment',
            'view_mode': 'list,form,calendar',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }

    def action_new_appointment(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nouveau Rendez-Vous',
            'res_model': 'medical.appointment',
            'view_mode': 'form',
            'context': {'default_patient_id': self.id},
        }
