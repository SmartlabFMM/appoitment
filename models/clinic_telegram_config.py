# -*- coding: utf-8 -*-
"""
Configuration Telegram pour le module clinic_appointment.
Stocke le token du bot et les paramètres de notification.
Accessible via : Configuration > Paramètres Telegram
"""
import requests
import logging

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class ClinicTelegramConfig(models.TransientModel):
    """
    Modèle de configuration Telegram (res.config.settings style).
    Utilise ir.config_parameter pour persister les valeurs.
    """
    _name  = 'clinic.telegram.config'
    _description = 'Configuration Telegram Clinique'
    _inherit = 'res.config.settings'

    # ── Paramètres Telegram ──────────────────────────────────────────────────
    telegram_bot_token = fields.Char(
        string='Token du Bot Telegram',
        config_parameter='clinic.telegram_bot_token',
        help='Token obtenu depuis @BotFather sur Telegram. Ex: 123456:ABC-DEF...',
    )
    telegram_bot_username = fields.Char(
        string='Username du Bot',
        config_parameter='clinic.telegram_bot_username',
        help='Username du bot sans @. Ex: MaCliniqueBot',
    )
    telegram_notifications_enabled = fields.Boolean(
        string='Activer les Notifications Telegram',
        config_parameter='clinic.telegram_notifications_enabled',
        default=False,
    )
    telegram_no_show_delay = fields.Integer(
        string='Délai Absence (minutes)',
        config_parameter='clinic.telegram_no_show_delay',
        default=30,
        help='Délai en minutes après lequel un RDV non pointé est marqué absent.',
    )

    # ── Test de connexion ────────────────────────────────────────────────────
    def action_test_telegram(self):
        """Teste la connexion au bot Telegram."""
        token = self.env['ir.config_parameter'].sudo().get_param('clinic.telegram_bot_token')
        if not token:
            raise UserError('Veuillez d\'abord configurer le token du bot Telegram.')
        try:
            resp = requests.get(
                f'https://api.telegram.org/bot{token}/getMe',
                timeout=10,
            )
            data = resp.json()
            if data.get('ok'):
                bot = data['result']
                raise UserError(
                    f'✅ Connexion réussie !\n'
                    f'Bot : @{bot.get("username")} ({bot.get("first_name")})'
                )
            else:
                raise UserError(f'❌ Erreur Telegram : {data.get("description", "Token invalide")}')
        except requests.RequestException as e:
            raise UserError(f'❌ Impossible de joindre Telegram : {str(e)}')
