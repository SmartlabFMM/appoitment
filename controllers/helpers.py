# -*- coding: utf-8 -*-
import json
import jwt
from odoo.http import request, Response

JWT_SECRET = '312005'

ALLOWED_ORIGINS = [
    'http://localhost:4200',
    'http://127.0.0.1:4200',
]

CORS_HEADERS = {
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Max-Age': '86400',
}


def _cors_origin():
    """Return the exact allowed origin for this request (never wildcard)."""
    try:
        origin = request.httprequest.headers.get('Origin', '')
    except Exception:
        origin = ''
    return origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0]


def options_response():
    """
    Explicit 200 OK for CORS preflight OPTIONS requests.
    Returns all required CORS headers with exact origin (not wildcard).
    """
    headers = dict(CORS_HEADERS)
    headers['Access-Control-Allow-Origin'] = _cors_origin()
    headers['Access-Control-Allow-Credentials'] = 'true'
    # Must return 200, not 204 — some browsers reject 204 for preflight
    return Response('OK', status=200, headers=headers)


def json_response(data, status=200):
    headers = dict(CORS_HEADERS)
    headers['Access-Control-Allow-Origin'] = _cors_origin()
    headers['Access-Control-Allow-Credentials'] = 'true'
    return Response(
        json.dumps(data, default=str),
        status=status,
        mimetype='application/json',
        headers=headers,
    )


def error_response(message, status=400):
    return json_response({'message': message}, status)


def get_body():
    try:
        return json.loads(request.httprequest.data.decode('utf-8'))
    except Exception:
        return {}


def verify_token():
    """Returns patient_id if JWT valid, else None."""
    try:
        auth_header = request.httprequest.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return None
        token = auth_header[7:]
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload.get('patient_id')
    except Exception:
        return None


def require_auth():
    """Returns (patient_id, None) or (None, error_response)."""
    pid = verify_token()
    if not pid:
        return None, error_response('Non authentifie. Veuillez vous connecter.', 401)
    try:
        patient = request.env['medical.patient'].sudo().browse(pid)
        if not patient.exists() or not patient.active:
            return None, error_response('Patient introuvable', 401)
        return pid, None
    except Exception as e:
        return None, error_response(f'Erreur auth: {str(e)}', 401)
