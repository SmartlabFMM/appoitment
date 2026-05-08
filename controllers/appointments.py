# -*- coding: utf-8 -*-
import json
from datetime import datetime
from odoo import http
from odoo.http import request
from .helpers import json_response, error_response, options_response, require_auth


def _fmt_time(value):
    h = int(value)
    m = round((value - h) * 60)
    return f'{h:02d}:{m:02d}'


def _appt_to_dict(a):
    return {
        'id':                       a.id,
        'name':                     a.name,
        'appointment_date':         str(a.appointment_date),
        'appointment_time':         a.appointment_time,
        'appointment_time_display': _fmt_time(a.appointment_time),
        'duration':                 a.duration or 30,
        'reason':                   a.reason or '',
        'symptoms':                 a.symptoms or '',
        'state':                    a.state,
        'priority':                 a.priority or '0',
        'appointment_type':         a.appointment_type or 'first',
        'diagnosis':                a.diagnosis or '',
        'prescription':             a.prescription or '',
        'doctor_name':              a.doctor_id.name,
        'doctor_title':             a.doctor_id.title or 'dr',
        'doctor_full_name':         f"{'Pr.' if a.doctor_id.title == 'pr' else 'Dr.'} {a.doctor_id.name}",
        'speciality_name':          a.speciality_id.name,
    }


class ClinicAppointmentController(http.Controller):

    @http.route([
        '/clinic/appointments',
        '/clinic/appointments/<int:appt_id>',
        '/clinic/appointments/<int:appt_id>/cancel',
    ], type='http', auth='none', methods=['OPTIONS'], csrf=False)
    def options(self, **kwargs):
        return options_response()

    @http.route('/clinic/appointments', type='http', auth='none',
                methods=['GET'], csrf=False)
    def get_appointments(self, **kwargs):
        patient_id, err = require_auth()
        if err:
            return err
        try:
            appts = request.env['medical.appointment'].sudo().search([
                ('patient_id', '=', patient_id),
            ], order='appointment_date desc, appointment_time desc')
            return json_response([_appt_to_dict(a) for a in appts])
        except Exception as e:
            return error_response(str(e), 500)

    @http.route('/clinic/appointments', type='http', auth='none',
                methods=['POST'], csrf=False)
    def create_appointment(self, **kwargs):
        patient_id, err = require_auth()
        if err:
            return err
        try:
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')

            required = ['doctor_id', 'speciality_id', 'appointment_date', 'appointment_time', 'reason']
            for field in required:
                if not data.get(field) and data.get(field) != 0:
                    return error_response(f'Champ requis manquant: {field}', 400)

            doctor_id        = int(data['doctor_id'])
            speciality_id    = int(data['speciality_id'])
            appointment_date = data['appointment_date']
            appointment_time = float(data['appointment_time'])
            reason           = data['reason'].strip()

            conflict = request.env['medical.appointment'].sudo().search_count([
                ('doctor_id', '=', doctor_id),
                ('appointment_date', '=', appointment_date),
                ('appointment_time', '=', appointment_time),
                ('state', 'not in', ['cancelled']),
            ])
            if conflict:
                return error_response('Ce creneau est deja reserve.', 409)

            doctor   = request.env['medical.doctor'].sudo().browse(doctor_id)
            duration = doctor.consultation_duration or 30

            count = request.env['medical.appointment'].sudo().search_count([])
            d     = datetime.now()
            ref   = f"RDV/{d.year}/{str(d.month).zfill(2)}/{str(count + 1).zfill(4)}"

            appt = request.env['medical.appointment'].sudo().create({
                'name':             ref,
                'patient_id':       patient_id,
                'doctor_id':        doctor_id,
                'speciality_id':    speciality_id,
                'appointment_date': appointment_date,
                'appointment_time': appointment_time,
                'duration':         duration,
                'reason':           reason,
                'symptoms':         data.get('symptoms') or '',
                'appointment_type': data.get('appointment_type') or 'first',
                'state':            'draft',
                'priority':         '0',
                'confirmation_sent': False,
                'reminder_sent':     False,
            })
            return json_response({
                'message':     'Rendez-vous cree avec succes! En attente de confirmation.',
                'appointment': _appt_to_dict(appt),
            }, 201)
        except Exception as e:
            return error_response(f'Erreur serveur: {str(e)}', 500)

    @http.route('/clinic/appointments/<int:appt_id>/cancel', type='http',
                auth='none', methods=['POST'], csrf=False)
    def cancel_appointment(self, appt_id, **kwargs):
        patient_id, err = require_auth()
        if err:
            return err
        try:
            appt = request.env['medical.appointment'].sudo().search([
                ('id', '=', appt_id),
                ('patient_id', '=', patient_id),
            ], limit=1)
            if not appt:
                return error_response('Rendez-vous introuvable', 404)
            if appt.state in ('done', 'cancelled'):
                return error_response('Ce rendez-vous ne peut pas etre annule', 400)
            appt.write({'state': 'cancelled'})
            return json_response({'message': 'Rendez-vous annule avec succes'})
        except Exception as e:
            return error_response(f'Erreur serveur: {str(e)}', 500)
