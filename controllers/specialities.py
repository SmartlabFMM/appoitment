# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from .helpers import json_response, error_response, options_response


class ClinicSpecialityController(http.Controller):

    @http.route([
        '/clinic/specialities',
        '/clinic/specialities/<int:spec_id>/doctors',
    ], type='http', auth='none', methods=['OPTIONS'], csrf=False)
    def options(self, **kwargs):
        return options_response()

    @http.route('/clinic/specialities', type='http', auth='none',
                methods=['GET'], csrf=False)
    def get_specialities(self, **kwargs):
        try:
            specs = request.env['medical.speciality'].sudo().search(
                [('active', '=', True)], order='name asc'
            )
            result = []
            for s in specs:
                doctor_count = request.env['medical.doctor'].sudo().search_count([
                    ('speciality_id', '=', s.id), ('active', '=', True),
                ])
                result.append({
                    'id':               s.id,
                    'name':             s.name,
                    'code':             s.code or '',
                    'description':      s.description or '',
                    'average_duration': s.average_duration or 30,
                    'doctor_count':     doctor_count,
                })
            return json_response(result)
        except Exception as e:
            return error_response(str(e), 500)

    @http.route('/clinic/specialities/<int:spec_id>/doctors', type='http',
                auth='none', methods=['GET'], csrf=False)
    def get_doctors_by_speciality(self, spec_id, **kwargs):
        try:
            doctors = request.env['medical.doctor'].sudo().search([
                ('speciality_id', '=', spec_id), ('active', '=', True),
            ], order='name asc')
            return json_response([{
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
            } for d in doctors])
        except Exception as e:
            return error_response(str(e), 500)
