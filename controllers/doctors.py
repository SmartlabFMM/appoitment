# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import http
from odoo.http import request
from .helpers import json_response, error_response, options_response


def _doctor_dict(d):
    return {
        'id':                    d.id,
        'name':                  d.name,
        'title':                 d.title or 'dr',
        'display_name_full':     d.display_name_full or d.name,
        'speciality_id':         d.speciality_id.id,
        'speciality_name':       d.speciality_id.name,
        'experience_years':      d.experience_years or 0,
        'consultation_duration': d.consultation_duration or 30,
        'consultation_fee':      d.consultation_fee or 0,
        'phone':                 d.phone or '',
        'email':                 d.email or '',
    }


class ClinicDoctorController(http.Controller):

    @http.route([
        '/clinic/doctors',
        '/clinic/doctors/<int:doctor_id>',
        '/clinic/doctors/<int:doctor_id>/slots',
    ], type='http', auth='none', methods=['OPTIONS'], csrf=False)
    def options(self, **kwargs):
        return options_response()

    @http.route('/clinic/doctors', type='http', auth='none',
                methods=['GET'], csrf=False)
    def get_doctors(self, **kwargs):
        try:
            params = request.httprequest.args
            domain = [('active', '=', True)]
            if params.get('speciality_id'):
                domain.append(('speciality_id', '=', int(params['speciality_id'])))
            if params.get('name'):
                domain.append(('name', 'ilike', params['name']))
            doctors = request.env['medical.doctor'].sudo().search(domain, order='name asc')
            return json_response([_doctor_dict(d) for d in doctors])
        except Exception as e:
            return error_response(str(e), 500)

    @http.route('/clinic/doctors/<int:doctor_id>', type='http', auth='none',
                methods=['GET'], csrf=False)
    def get_doctor(self, doctor_id, **kwargs):
        try:
            d = request.env['medical.doctor'].sudo().browse(doctor_id)
            if not d.exists() or not d.active:
                return error_response('Medecin introuvable', 404)
            return json_response(_doctor_dict(d))
        except Exception as e:
            return error_response(str(e), 500)

    @http.route('/clinic/doctors/<int:doctor_id>/slots', type='http', auth='none',
                methods=['GET'], csrf=False)
    def get_slots(self, doctor_id, **kwargs):
        try:
            date_str = request.httprequest.args.get('date')
            if not date_str:
                return error_response('Parametre date requis', 400)

            date_obj    = datetime.strptime(date_str, '%Y-%m-%d').date()
            day_of_week = str(date_obj.weekday())

            doctor = request.env['medical.doctor'].sudo().browse(doctor_id)
            if not doctor.exists() or not doctor.active:
                return error_response('Medecin introuvable', 404)

            schedules = request.env['medical.schedule'].sudo().search([
                ('doctor_id', '=', doctor_id),
                ('day_of_week', '=', day_of_week),
                ('active', '=', True),
            ])
            if not schedules:
                return json_response({
                    'slots': [], 'duration': doctor.consultation_duration or 30,
                    'message': 'Medecin non disponible ce jour',
                })

            booked_times = set(
                request.env['medical.appointment'].sudo().search([
                    ('doctor_id', '=', doctor_id),
                    ('appointment_date', '=', date_str),
                    ('state', 'not in', ['cancelled']),
                ]).mapped('appointment_time')
            )

            duration   = doctor.consultation_duration or 30
            duration_h = duration / 60.0
            slots      = []

            for sched in schedules:
                current = float(sched.start_time)
                end     = float(sched.end_time)
                while round(current + duration_h, 4) <= end:
                    if current not in booked_times:
                        h = int(current)
                        m = round((current - h) * 60)
                        slots.append({'value': current, 'label': f'{h:02d}:{m:02d}'})
                    current = round(current + duration_h, 4)

            return json_response({'slots': slots, 'duration': duration})
        except Exception as e:
            return error_response(str(e), 500)
