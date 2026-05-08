# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class MedicalAppointment(models.Model):
    _name = 'medical.appointment'
    _description = 'Rendez-Vous Médical'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'appointment_date desc, appointment_time desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
    )

    # Acteurs
    patient_id = fields.Many2one(
        'medical.patient',
        string='Patient',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    doctor_id = fields.Many2one(
        'medical.doctor',
        string='Médecin',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    # speciality_id = fields.Many2one(
    #     'medical.speciality',
    #     string='Spécialité',
    #     required=True,
    #     tracking=True,
    #     ondelete='restrict',
    # )

    # Date et heure
    appointment_date = fields.Date(
        string='Date du Rendez-Vous',
        required=True,
        tracking=True,
    )
    appointment_time = fields.Float(
        string='Heure du Rendez-Vous',
        required=True,
        tracking=True,
    )
    appointment_time_display = fields.Char(
        string='Heure',
        compute='_compute_time_display',
    )
    # duration = fields.Integer(
    #     string='Durée (min)',
    #     default=30,
    #     tracking=True,
    # )
    appointment_datetime = fields.Datetime(
        string='Date/Heure Complète',
        compute='_compute_appointment_datetime',
        store=True,
    )
    end_datetime = fields.Datetime(
        string='Fin',
        compute='_compute_appointment_datetime',
        store=True,
    )

    # État
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('waiting', 'En Attente'),
        ('in_progress', 'En Cours'),
        ('done', 'Terminé'),
        ('cancelled', 'Annulé'),
        ('no_show', 'Absent'),
    ], string='État', default='draft', tracking=True, required=True)

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Urgent'),
        ('2', 'Très Urgent'),
    ], string='Priorité', default='0', tracking=True)

    # Motif et notes
    reason = fields.Text(
        string='Motif de la Consultation',
        required=True,
    )
    symptoms = fields.Text(string='Symptômes Décrits')
    diagnosis = fields.Text(string='Diagnostic', tracking=True)
    prescription = fields.Text(string='Ordonnance / Prescription')
    doctor_notes = fields.Text(string='Notes du Médecin')
    secretary_notes = fields.Text(string='Notes de la Secrétaire')

    # Informations complémentaires
    appointment_type = fields.Selection([
        ('first', 'Première Visite'),
        ('followup', 'Suivi'),
        ('emergency', 'Urgence'),
        ('control', 'Contrôle'),
    ], string='Type de Consultation', default='first', tracking=True)

    is_urgent = fields.Boolean(
        string='Urgence',
        compute='_compute_is_urgent',
        store=True,
    )

    confirmation_sent = fields.Boolean(
        string='Confirmation Envoyée',
        default=False,
    )
    reminder_sent = fields.Boolean(
        string='Rappel Envoyé',
        default=False,
    )

    # Champs calculés
    duration = fields.Integer(
        related='doctor_id.consultation_duration',
        string='Durée (min)',
    )

    speciality_id = fields.Char(
        related='doctor_id.speciality_id.name',
        string='Spécialité',
    )

    patient_phone = fields.Char(
        related='patient_id.phone',
        string='Téléphone Patient',
    )
    patient_age = fields.Integer(
        related='patient_id.age',
        string='Âge Patient',
    )
    patient_blood_group = fields.Selection(
        related='patient_id.blood_group',
        string='Groupe Sanguin',
    )
    color = fields.Integer(
        string='Couleur',
        compute='_compute_color',
    )

    # ------------------------------------------------
    # Constraintes SQL
    # ------------------------------------------------
    _sql_constraints = [
        ('unique_doctor_slot', 'UNIQUE(doctor_id, appointment_date, appointment_time)',
         'Ce créneau est déjà réservé pour ce médecin!'),
    ]

    # ------------------------------------------------
    # Computed Methods
    # ------------------------------------------------

    @api.depends('appointment_time')
    def _compute_time_display(self):
        for rec in self:
            if rec.appointment_time:
                hours = int(rec.appointment_time)
                minutes = int((rec.appointment_time - hours) * 60)
                rec.appointment_time_display = f"{hours:02d}:{minutes:02d}"
            else:
                rec.appointment_time_display = ''

    @api.depends('appointment_date', 'appointment_time', 'duration')
    def _compute_appointment_datetime(self):
        for rec in self:
            if rec.appointment_date and rec.appointment_time:
                hours = int(rec.appointment_time)
                minutes = int((rec.appointment_time - hours) * 60)
                dt = datetime.combine(rec.appointment_date, datetime.min.time()).replace(
                    hour=hours, minute=minutes
                )
                rec.appointment_datetime = dt
                rec.end_datetime = dt + timedelta(minutes=rec.duration or 30)
            else:
                rec.appointment_datetime = False
                rec.end_datetime = False

    @api.depends('priority')
    def _compute_is_urgent(self):
        for rec in self:
            rec.is_urgent = rec.priority in ('1', '2')

    def _compute_color(self):
        color_map = {
            'draft': 0,
            'confirmed': 10,
            'waiting': 2,
            'in_progress': 4,
            'done': 20,
            'cancelled': 9,
            'no_show': 1,
        }
        for rec in self:
            rec.color = color_map.get(rec.state, 0)

    # ------------------------------------------------
    # ORM
    # ------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.appointment') or 'Nouveau'
            # Hériter de la durée du médecin si non spécifiée
            if 'duration' not in vals and vals.get('doctor_id'):
                doctor = self.env['medical.doctor'].browse(vals['doctor_id'])
                vals['duration'] = doctor.consultation_duration
        return super().create(vals_list)

    # ------------------------------------------------
    # Onchange
    # ------------------------------------------------

    # @api.onchange('speciality_id')
    # def _onchange_speciality(self):
    #     if self.speciality_id:
    #         self.doctor_id = False
    #         return {'domain': {'doctor_id': [('speciality_id', '=', self.speciality_id.id), ('active', '=', True)]}}
    #
    # @api.onchange('doctor_id')
    # def _onchange_doctor(self):
    #     if self.doctor_id:
    #         self.duration = self.doctor_id.consultation_duration
    #         if not self.speciality_id:
    #             self.speciality_id = self.doctor_id.speciality_id

    # ------------------------------------------------
    # Constraintes
    # ------------------------------------------------

    @api.constrains('appointment_date')
    def _check_appointment_date(self):
        for rec in self:
            if rec.appointment_date and rec.appointment_date < fields.Date.today():
                if rec.state == 'draft':
                    raise ValidationError("La date du rendez-vous ne peut pas être dans le passé!")

    @api.constrains('appointment_time')
    def _check_appointment_time(self):
        for rec in self:
            if rec.appointment_time < 0 or rec.appointment_time >= 24:
                raise ValidationError("L'heure du rendez-vous doit être entre 00:00 et 23:59!")

    @api.constrains('doctor_id', 'appointment_date', 'appointment_time')
    def _check_doctor_availability(self):
        for rec in self:
            if not rec.doctor_id or not rec.appointment_date or not rec.appointment_time:
                continue
            # Vérifier si le médecin a un planning pour ce jour
            day_of_week = str(rec.appointment_date.weekday())
            schedule = self.env['medical.schedule'].search([
                ('doctor_id', '=', rec.doctor_id.id),
                ('day_of_week', '=', day_of_week),
                ('active', '=', True),
                ('start_time', '<=', rec.appointment_time),
                ('end_time', '>=', rec.appointment_time + (rec.duration / 60.0)),
            ])
            if not schedule:
                raise ValidationError(
                    f"Le médecin {rec.doctor_id.display_name_full} n'est pas disponible "
                    f"à cette date/heure selon son planning!"
                )

    # ------------------------------------------------
    # Actions / Workflow
    # ------------------------------------------------

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Seuls les rendez-vous en brouillon peuvent être confirmés.")
            rec.state = 'confirmed'
            rec._send_confirmation_email()

    def action_waiting(self):
        for rec in self:
            rec.state = 'waiting'

    def action_in_progress(self):
        for rec in self:
            if rec.state not in ('confirmed', 'waiting'):
                raise UserError("Le rendez-vous doit être confirmé ou en attente.")
            rec.state = 'in_progress'

    def action_done(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError("Le rendez-vous doit être en cours pour être terminé.")
            rec.state = 'done'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError("Un rendez-vous terminé ne peut pas être annulé.")
            rec.state = 'cancelled'
            rec.message_post(body="Rendez-vous annulé.")

    def action_no_show(self):
        for rec in self:
            rec.state = 'no_show'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    def _send_confirmation_email(self):
        # self.ensure_one()
        # template_msg = f"""
        # <p>Cher(e) <strong>{self.patient_id.name}</strong>,</p>
        # <p>Votre rendez-vous a été <strong>confirmé</strong> :</p>
        # <ul>
        #     <li><strong>Médecin :</strong> {self.doctor_id.display_name_full}</li>
        #     <li><strong>Spécialité :</strong> {self.speciality_id.name}</li>
        #     <li><strong>Date :</strong> {self.appointment_date}</li>
        #     <li><strong>Heure :</strong> {self.appointment_time_display}</li>
        # </ul>
        # <p>Merci de vous présenter 30 minutes avant l'heure prévue.</p>
        # """
        # self.message_post(
        #     body=template_msg,
        #     subject=f"Confirmation Rendez-Vous {self.name}",
        #     message_type='notification',
        # )
        # self.confirmation_sent = True

        mail_values = {
            'subject': 'Confirmation Rendez-vous',
            'body_html': f"""
                        <p>Cher(e) <strong>{self.patient_id.name}</strong>,</p>
                        <p>Votre rendez-vous a été <strong>confirmé</strong> :</p>
                        <ul>
                            <li><strong>Médecin :</strong> {self.doctor_id.display_name_full}</li>
                            <li><strong>Spécialité :</strong> {self.speciality_id}</li>
                            <li><strong>Date :</strong> {self.appointment_date}</li>
                            <li><strong>Heure :</strong> {self.appointment_time_display}</li>
                        </ul>
                        <p>Merci de vous présenter 30 minutes avant l'heure prévue.</p>
                    """,
            'email_to': self.patient_id.email,
            'email_from': 'arafettekaya@gmail.com',
        }

        self.env['mail.mail'].create(mail_values).send()

    def action_print_appointment(self):
        return self.env.ref('clinic_appointment.action_appointment_report').report_action(self)

    # ------------------------------------------------
    # Dashboard / Stats
    # ------------------------------------------------

    @api.model
    def get_dashboard_stats(self):
        today = fields.Date.today()
        return {
            'today_total': self.search_count([('appointment_date', '=', today), ('state', 'not in', ['cancelled'])]),
            'today_confirmed': self.search_count([('appointment_date', '=', today), ('state', '=', 'confirmed')]),
            'today_done': self.search_count([('appointment_date', '=', today), ('state', '=', 'done')]),
            'today_waiting': self.search_count([('appointment_date', '=', today), ('state', '=', 'waiting')]),
            'month_total': self.search_count([
                ('appointment_date', '>=', today.replace(day=1)),
                ('state', 'not in', ['cancelled']),
            ]),
            'urgent_pending': self.search_count([
                ('priority', 'in', ('1', '2')),
                ('state', 'not in', ['done', 'cancelled']),
                ('appointment_date', '>=', today),
            ]),
        }
