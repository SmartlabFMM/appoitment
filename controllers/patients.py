# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request
from .helpers import json_response, error_response, options_response, require_auth
from .auth import _normalize_governorate


def _patient_full_dict(p):
    return {
        'id':               p.id,
        'name':             p.name,
        'ref':              p.ref or '',
        'gender':           p.gender or '',
        'birth_date':       str(p.birth_date) if p.birth_date else '',
        'phone':            p.phone or '',
        'email':            p.email or '',
        'address':          p.address or '',
        'city':             p.city or '',
        'governorate':      p.governorate or '',
        'blood_group':      p.blood_group or '',
        'insurance_type':   p.insurance_type or 'none',
        'insurance_number': p.insurance_number or '',
        'allergies':        p.allergies or '',
        'chronic_diseases': p.chronic_diseases or '',
    }


class ClinicPatientController(http.Controller):

    @http.route('/clinic/patients/me', type='http', auth='none',
                methods=['OPTIONS'], csrf=False)
    def options(self, **kwargs):
        return options_response()

    @http.route('/clinic/patients/me', type='http', auth='none',
                methods=['GET'], csrf=False)
    def get_profile(self, **kwargs):
        patient_id, err = require_auth()
        if err:
            return err
        try:
            patient = request.env['medical.patient'].sudo().browse(patient_id)
            if not patient.exists():
                return error_response('Patient introuvable', 404)
            return json_response(_patient_full_dict(patient))
        except Exception as e:
            return error_response(f'Erreur serveur: {str(e)}', 500)

    @http.route('/clinic/patients/me', type='http', auth='none',
                methods=['PUT'], csrf=False)
    def update_profile(self, **kwargs):
        patient_id, err = require_auth()
        if err:
            return err
        try:
            data    = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            patient = request.env['medical.patient'].sudo().browse(patient_id)
            if not patient.exists():
                return error_response('Patient introuvable', 404)

            allowed = [
                'phone', 'address', 'city', 'blood_group',
                'insurance_type', 'insurance_number',
                'allergies', 'chronic_diseases',
            ]
            vals = {k: data[k] for k in allowed if k in data}
            if data.get('governorate'):
                vals['governorate'] = _normalize_governorate(data['governorate'])

            if vals:
                patient.write(vals)
            return json_response({'message': 'Profil mis a jour avec succes'})
        except Exception as e:
            return error_response(f'Erreur serveur: {str(e)}', 500)
