# -*- coding: utf-8 -*-
"""
Override ir.http to handle CORS preflight OPTIONS requests
at the middleware level — before Odoo's own routing logic runs.

This ensures OPTIONS always returns 200 with correct CORS headers,
even if Odoo would otherwise crash or return a non-2xx status.

Place this file in your module's models/ folder and add
'from . import ir_http' to models/__init__.py
"""
from odoo import models
from odoo.http import request, Response

ALLOWED_ORIGINS = [
    'http://localhost:4200',
    'http://127.0.0.1:4200',
]

CLINIC_PREFIXES = (
    '/clinic/',
)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls, endpoint):
        """Intercept OPTIONS preflight for /clinic/* routes."""
        try:
            method = request.httprequest.method
            path   = request.httprequest.path

            if method == 'OPTIONS' and any(path.startswith(p) for p in CLINIC_PREFIXES):
                origin = request.httprequest.headers.get('Origin', '')
                allowed = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0]
                return Response('OK', status=200, headers={
                    'Access-Control-Allow-Origin':      allowed,
                    'Access-Control-Allow-Credentials': 'true',
                    'Access-Control-Allow-Headers':     'Content-Type, Authorization',
                    'Access-Control-Allow-Methods':     'GET, POST, PUT, DELETE, OPTIONS',
                    'Access-Control-Max-Age':           '86400',
                })
        except Exception:
            pass

        return super()._dispatch(endpoint)
