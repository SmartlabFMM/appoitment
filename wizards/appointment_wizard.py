# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date


class AppointmentWizard(models.TransientModel):
    """
    Assistant de prise de rendez-vous rapide.
    Guide le patient/secrétaire en 3 étapes :
    1. Choisir la spécialité
    2. Choisir le médecin et la date
    3. Choisir le créneau horaire
    """
    _name = 'appointment.wizard'
    _description = 'Assistant de Prise de Rendez-Vous'

    # Étape 1 : Spécialité
    speciality_id = fields.Many2one(
        'medical.speciality',
        string='Spécialité Médicale',
        required=True,
    )

    # Étape 2 : Médecin et Date
    doctor_id = fields.Many2one(
        'medical.doctor',
        string='Médecin',
        required=True,
        domain="[('speciality_id', '=', speciality_id), ('active', '=', True)]",
    )
    appointment_date = fields.Date(
        string='Date du Rendez-Vous',
        required=True,
        default=fields.Date.today,
    )

    # Étape 3 : Créneau horaire
    appointment_time = fields.Float(
        string='Heure',
        required=True,
    )
    appointment_time_display = fields.Char(
        string='Heure Affichée',
        compute='_compute_time_display',
    )

    # Patient
    patient_id = fields.Many2one(
        'medical.patient',
        string='Patient',
        required=True,
    )

    # Informations complémentaires
    reason = fields.Text(
        string='Motif',
        required=True,
        placeholder="Décrivez le motif de la consultation...",
    )
    appointment_type = fields.Selection([
        ('first', 'Première Visite'),
        ('followup', 'Suivi'),
        ('emergency', 'Urgence'),
        ('control', 'Contrôle'),
    ], string='Type', default='first', required=True)
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Urgent'),
        ('2', 'Très Urgent'),
    ], string='Priorité', default='0')

    # Info calculées
    doctor_info = fields.Char(
        string='Info Médecin',
        compute='_compute_doctor_info',
    )
    available_slots_info = fields.Char(
        string='Créneaux Disponibles',
        compute='_compute_available_slots_info',
    )

    @api.depends('appointment_time')
    def _compute_time_display(self):
        for rec in self:
            if rec.appointment_time:
                h = int(rec.appointment_time)
                m = int((rec.appointment_time - h) * 60)
                rec.appointment_time_display = f"{h:02d}:{m:02d}"
            else:
                rec.appointment_time_display = '--:--'

    @api.depends('doctor_id')
    def _compute_doctor_info(self):
        for rec in self:
            if rec.doctor_id:
                rec.doctor_info = (
                    f"{rec.doctor_id.display_name_full} | "
                    f"Durée consultation: {rec.doctor_id.consultation_duration} min"
                )
            else:
                rec.doctor_info = ''

    @api.depends('doctor_id', 'appointment_date')
    def _compute_available_slots_info(self):
        for rec in self:
            if rec.doctor_id and rec.appointment_date:
                slots = rec.doctor_id.get_available_slots(rec.appointment_date)
                rec.available_slots_info = f"{len(slots)} créneau(x) disponible(s)"
            else:
                rec.available_slots_info = ''

    @api.onchange('speciality_id')
    def _onchange_speciality(self):
        self.doctor_id = False
        self.appointment_time = 0

    @api.onchange('doctor_id', 'appointment_date')
    def _onchange_doctor_date(self):
        self.appointment_time = 0

    @api.constrains('appointment_date')
    def _check_date(self):
        for rec in self:
            if rec.appointment_date < date.today():
                raise ValidationError("La date du rendez-vous ne peut pas être dans le passé!")

    def action_confirm_appointment(self):
        """Créer le rendez-vous et ouvrir la fiche."""
        self.ensure_one()

        # Vérifier disponibilité
        existing = self.env['medical.appointment'].search_count([
            ('doctor_id', '=', self.doctor_id.id),
            ('appointment_date', '=', self.appointment_date),
            ('appointment_time', '=', self.appointment_time),
            ('state', 'not in', ['cancelled']),
        ])
        if existing:
            raise ValidationError(
                f"Ce créneau ({self.appointment_time_display}) est déjà réservé "
                f"pour le Dr {self.doctor_id.name}. Veuillez choisir un autre créneau."
            )

        appointment = self.env['medical.appointment'].create({
            'patient_id': self.patient_id.id,
            'doctor_id': self.doctor_id.id,
            'speciality_id': self.speciality_id.id,
            'appointment_date': self.appointment_date,
            'appointment_time': self.appointment_time,
            'duration': self.doctor_id.consultation_duration,
            'reason': self.reason,
            'appointment_type': self.appointment_type,
            'priority': self.priority,
            'state': 'draft',
        })

        # Ouvrir la fiche du rendez-vous créé
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rendez-Vous Créé',
            'res_model': 'medical.appointment',
            'res_id': appointment.id,
            'view_mode': 'form',
            'target': 'current',
        }


class BulkCancelWizard(models.TransientModel):
    """
    Assistant d'annulation en masse de rendez-vous.
    """
    _name = 'bulk.cancel.wizard'
    _description = 'Annulation en Masse'

    reason = fields.Text(
        string='Motif d\'Annulation',
        required=True,
        placeholder="Indiquez la raison de l'annulation...",
    )
    appointment_ids = fields.Many2many(
        'medical.appointment',
        string='Rendez-Vous à Annuler',
        default=lambda self: self.env['medical.appointment'].browse(
            self.env.context.get('active_ids', [])
        ),
    )
    count = fields.Integer(
        string='Nombre de RDV',
        compute='_compute_count',
    )

    @api.depends('appointment_ids')
    def _compute_count(self):
        for rec in self:
            rec.count = len(rec.appointment_ids)

    def action_bulk_cancel(self):
        for appt in self.appointment_ids:
            if appt.state != 'done':
                appt.state = 'cancelled'
                appt.message_post(
                    body=f"Annulé en masse. Motif : {self.reason}"
                )
        return {'type': 'ir.actions.act_window_close'}
