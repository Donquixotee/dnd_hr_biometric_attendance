# -*- coding: utf-8 -*-
# This module and its content is copyright of DND Consulting.
# - © DND Consulting 2025. All rights reserved.

from odoo import api, fields, models


class DeviceUserCache(models.TransientModel):
    """Temporary cache model to store device users for selection."""
    _name = 'device.user.cache'
    _description = 'Device User Cache'
    _rec_name = 'display_name'

    device_id = fields.Many2one('biometric.config', string='Device', required=True)
    user_id = fields.Char(string='Device User ID', required=True)
    name = fields.Char(string='User Name')
    card = fields.Char(string='Card Number')
    uid = fields.Integer(string='Device UID')
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    is_linked = fields.Boolean(string='Already Linked', default=False, store=True)

    @api.depends('name', 'user_id', 'card')
    def _compute_display_name(self):
        """Compute display name for selection."""
        for record in self:
            card_display = record.card if record.card else 'N/A'
            record.display_name = f"{record.name} (ID: {record.user_id}, Card: {card_display})"
