# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MedicalSpeciality(models.Model):
    _name = 'medical.speciality'
    _description = 'Spécialité Médicale'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    # Fields
    name = fields.Char(
        string='Nom de la Spécialité',
        required=True,
        tracking=True,
        translate=True,
    )
    code = fields.Char(
        string='Code',
        required=True,
        copy=False,  # Prevent duplication
    )
    description = fields.Text(
        string='Description',
    )
    average_duration = fields.Integer(
        string='Durée Moyenne de Consultation (min)',
        default=30,
        help='Durée par défaut d\'une consultation pour cette spécialité',
    )
    color = fields.Integer(
        string='Couleur',
        default=0,
    )
    image = fields.Binary(
        string='Image',
        attachment=True,
    )

    # Archiving
    active = fields.Boolean(
        string='Actif',
        default=True,
        tracking=True,
    )

    # Relations
    doctor_ids = fields.One2many(
        'medical.doctor',
        'speciality_id',
        string='Médecins',
    )

    # Computed Fields
    doctor_count = fields.Integer(
        string='Nombre de Médecins',
        compute='_compute_doctor_count',
        store=True,
    )
    appointment_count = fields.Integer(
        string='Nombre de Rendez-Vous',
        compute='_compute_appointment_count',
    )

    # Validations in Data Tier (SQL Constraints)
    _code_unique = models.Constraint('UNIQUE(code)', 'Le code de la spécialité doit être unique!')
    _name_unique = models.Constraint('UNIQUE(name)', 'Le nom de la spécialité doit être unique!')

    # Methods for Computed Fields
    @api.depends('doctor_ids')
    def _compute_doctor_count(self):
        for rec in self:
            rec.doctor_count = len(rec.doctor_ids)

    def _compute_appointment_count(self):
        for rec in self:
            rec.appointment_count = self.env['medical.appointment'].search_count([
                ('speciality_id', '=', rec.id)
            ])

    # Validation in Logic Tier
    @api.constrains('average_duration')
    def _check_average_duration(self):
        for rec in self:
            if rec.average_duration <= 0:
                raise ValidationError("La durée moyenne doit être supérieure à 0 minutes.")

    # Buttons Actions
    def action_view_doctors(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Médecins - {self.name}',
            'res_model': 'medical.doctor',
            'view_mode': 'list,form',
            'domain': [('speciality_id', '=', self.id)],
            'context': {'default_speciality_id': self.id},
        }

    def action_view_appointments(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Rendez-Vous - {self.name}',
            'res_model': 'medical.appointment',
            'view_mode': 'list,form,calendar',
            'domain': [('speciality_id', '=', self.id)],
        }
