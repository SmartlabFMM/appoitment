# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MedicalSchedule(models.Model):
    _name = 'medical.schedule'
    _description = 'Planning Médecin'
    _inherit = ['mail.thread']
    _order = 'doctor_id, day_of_week, start_time'

    name = fields.Char(
        string='Libellé',
        compute='_compute_name',
        store=True,
    )
    doctor_id = fields.Many2one(
        'medical.doctor',
        string='Médecin',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    speciality_id = fields.Many2one(
        related='doctor_id.speciality_id',
        string='Spécialité',
        store=True,
    )
    day_of_week = fields.Selection([
        ('0', 'Lundi'),
        ('1', 'Mardi'),
        ('2', 'Mercredi'),
        ('3', 'Jeudi'),
        ('4', 'Vendredi'),
        ('5', 'Samedi'),
        ('6', 'Dimanche'),
    ], string='Jour de la Semaine', required=True, tracking=True)

    start_time = fields.Float(
        string='Heure de Début',
        required=True,
        tracking=True,
    )
    end_time = fields.Float(
        string='Heure de Fin',
        required=True,
        tracking=True,
    )
    start_time_display = fields.Char(
        string='Début',
        compute='_compute_time_display',
    )
    end_time_display = fields.Char(
        string='Fin',
        compute='_compute_time_display',
    )

    max_appointments = fields.Integer(
        string='Nombre Max de RDV',
        compute='_compute_max_appointments',
        store=True,
    )
    active = fields.Boolean(string='Actif', default=True, tracking=True)
    notes = fields.Text(string='Notes')

    @api.depends('doctor_id', 'day_of_week', 'start_time', 'end_time')
    def _compute_name(self):
        days = dict(self._fields['day_of_week'].selection)
        for rec in self:
            day_label = days.get(rec.day_of_week, '')
            hours_start = int(rec.start_time)
            minutes_start = int((rec.start_time - hours_start) * 60)
            hours_end = int(rec.end_time)
            minutes_end = int((rec.end_time - hours_end) * 60)
            rec.name = (
                f"{rec.doctor_id.name} - {day_label} "
                f"{hours_start:02d}:{minutes_start:02d}-{hours_end:02d}:{minutes_end:02d}"
            )

    @api.depends('start_time', 'end_time')
    def _compute_time_display(self):
        for rec in self:
            h_s = int(rec.start_time)
            m_s = int((rec.start_time - h_s) * 60)
            h_e = int(rec.end_time)
            m_e = int((rec.end_time - h_e) * 60)
            rec.start_time_display = f"{h_s:02d}:{m_s:02d}"
            rec.end_time_display = f"{h_e:02d}:{m_e:02d}"

    @api.depends('start_time', 'end_time', 'doctor_id.consultation_duration')
    def _compute_max_appointments(self):
        for rec in self:
            if rec.end_time > rec.start_time and rec.doctor_id.consultation_duration:
                duration_hours = rec.doctor_id.consultation_duration / 60.0
                rec.max_appointments = int((rec.end_time - rec.start_time) / duration_hours)
            else:
                rec.max_appointments = 0

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if rec.start_time >= rec.end_time:
                raise ValidationError("L'heure de début doit être avant l'heure de fin!")
            if rec.start_time < 0 or rec.end_time > 24:
                raise ValidationError("Les heures doivent être entre 00:00 et 24:00!")

    @api.constrains('doctor_id', 'day_of_week', 'start_time', 'end_time')
    def _check_overlap(self):
        for rec in self:
            overlapping = self.search([
                ('doctor_id', '=', rec.doctor_id.id),
                ('day_of_week', '=', rec.day_of_week),
                ('id', '!=', rec.id),
                ('active', '=', True),
            ])
            for other in overlapping:
                if (rec.start_time < other.end_time and rec.end_time > other.start_time):
                    raise ValidationError(
                        f"Ce planning chevauche un planning existant pour "
                        f"{rec.doctor_id.name} le {dict(self._fields['day_of_week'].selection).get(rec.day_of_week)}!"
                    )
