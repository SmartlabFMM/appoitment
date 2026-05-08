# -*- coding: utf-8 -*-
import json
import jwt
from datetime import datetime, timedelta
from odoo import http
from odoo.http import request, Response
from .helpers import json_response, error_response, options_response

JWT_SECRET = '312005'
JWT_EXPIRY_DAYS = 7

ALLOWED_ORIGINS = [
    'http://localhost:4200',
    'http://127.0.0.1:4200',
]

# Maps Angular UI labels to Odoo Selection keys
GOVERNORATE_MAP = {
    'Tunis': 'tunis', 'Ariana': 'ariana', 'Ben Arous': 'ben_arous',
    'Manouba': 'manouba', 'Nabeul': 'nabeul', 'Zaghouan': 'zaghouan',
    'Bizerte': 'bizerte', 'Béja': 'beja', 'Jendouba': 'jendouba',
    'Le Kef': 'kef', 'Siliana': 'siliana', 'Sousse': 'sousse',
    'Monastir': 'monastir', 'Mahdia': 'mahdia', 'Sfax': 'sfax',
    'Kairouan': 'kairouan', 'Kasserine': 'kasserine', 'Sidi Bouzid': 'sidi_bouzid',
    'Gabès': 'gabes', 'Médenine': 'medenine', 'Tataouine': 'tataouine',
    'Gafsa': 'gafsa', 'Tozeur': 'tozeur', 'Kébili': 'kebili',
}


def _normalize_governorate(value: str) -> str:
    if not value:
        return value
    if value in GOVERNORATE_MAP.values():
        return value
    return GOVERNORATE_MAP.get(value, value)


def _hash_password(password: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    except ImportError:
        raise ImportError(
            "Le module 'bcrypt' n'est pas installe. "
            "Executez: pip install bcrypt --break-system-packages"
        )


def _check_password(password: str, hashed: str) -> bool:
    try:
        import bcrypt
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except ImportError:
        raise ImportError(
            "Le module 'bcrypt' n'est pas installe. "
            "Executez: pip install bcrypt --break-system-packages"
        )


def _generate_token(patient_id, email):
    payload = {
        'patient_id': patient_id,
        'email':      email,
        'exp':        datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS),
        'iat':        datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def _patient_to_dict(p):
    return {
        'id':          p.id,
        'name':        p.name,
        'ref':         p.ref or '',
        'email':       p.email or '',
        'phone':       p.phone or '',
        'birth_date':  str(p.birth_date) if p.birth_date else '',
        'gender':      p.gender or '',
        'governorate': p.governorate or '',
    }


class ClinicAuthController(http.Controller):

    @http.route(['/clinic/auth/register', '/clinic/auth/login'],
                type='http', auth='none', methods=['OPTIONS'], csrf=False)
    def options_auth(self, **kwargs):
        return options_response()

    @http.route('/clinic/auth/register', type='http', auth='none',
                methods=['POST'], csrf=False)
    def register(self, **kwargs):
        try:
            data     = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            name     = (data.get('name') or '').strip()
            email    = (data.get('email') or '').strip().lower()
            phone    = (data.get('phone') or '').strip()
            password = data.get('password') or ''

            if not name:
                return error_response('Nom requis', 400)
            if not email or '@' not in email:
                return error_response('Email invalide', 400)
            if not phone:
                return error_response('Telephone requis', 400)
            if not password or len(password) < 6:
                return error_response('Mot de passe requis (min. 6 caracteres)', 400)

            existing = request.env['medical.patient'].sudo().search(
                [('email', '=', email)], limit=1
            )
            if existing:
                return error_response('Cet email est deja utilise', 409)

            hashed = _hash_password(password)
            count  = request.env['medical.patient'].sudo().search_count([])
            ref    = f"PAT/{datetime.now().year}/{str(count + 1).zfill(5)}"

            vals = {
                'name':           name,
                'email':          email,
                'phone':          phone,
                'ref':            ref,
                'password_hash':  hashed,
                'active':         True,
                'insurance_type': 'none',
            }
            for f in ['cin', 'birth_date', 'gender', 'mobile']:
                if data.get(f):
                    vals[f] = data[f]
            if data.get('governorate'):
                vals['governorate'] = _normalize_governorate(data['governorate'])

            patient = request.env['medical.patient'].sudo().create(vals)
            token   = _generate_token(patient.id, email)

            return json_response({
                'message': 'Compte cree avec succes',
                'token':   token,
                'patient': _patient_to_dict(patient),
            }, 201)

        except ImportError as e:
            return error_response(str(e), 500)
        except Exception as e:
            return error_response(f'Erreur serveur: {str(e)}', 500)

    @http.route('/clinic/auth/login', type='http', auth='none',
                methods=['POST'], csrf=False)
    def login(self, **kwargs):
        try:
            data  = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            email = (data.get('email') or '').strip().lower()
            pwd   = data.get('password') or ''

            if not email or not pwd:
                return error_response('Email et mot de passe requis', 400)

            patient = request.env['medical.patient'].sudo().search(
                [('email', '=', email), ('active', '=', True)], limit=1
            )
            if not patient or not patient.password_hash:
                return error_response('Email ou mot de passe incorrect', 401)

            if not _check_password(pwd, patient.password_hash):
                return error_response('Email ou mot de passe incorrect', 401)

            token = _generate_token(patient.id, email)
            return json_response({
                'message': 'Connexion reussie',
                'token':   token,
                'patient': _patient_to_dict(patient),
            })

        except ImportError as e:
            return error_response(str(e), 500)
        except Exception as e:
            return error_response(f'Erreur serveur: {str(e)}', 500)
