# -*- coding: utf-8 -*-
# This module and its content is copyright of DND Consulting.
# - © DND Consulting 2025. All rights reserved.

import logging
import unicodedata

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

DEVICE_NAME_LIMIT = 24
BADGE_DIGIT_LIMIT = 9


class HrEmployee(models.Model):
    """Inherits HrEmployee model to include a relationship with biometric devices"""
    _inherit = 'hr.employee'

    biometric_device_ids = fields.One2many('biometric.attendance.devices', 'employee_id', string='Biometric Devices')
    card_number = fields.Char(string="Card Number", groups="hr.group_hr_user", copy=False,
                              help="This card number is used for authentication purposes and will be passed to the biometric device")

    biometric_sync_state = fields.Selection([('no_badge', 'Needs a badge number'),
                                             ('waiting', 'Waiting to be sent'),
                                             ('partial', 'On some readers'),
                                             ('synced', 'On all readers')],
                                            string='Biometric Status',
                                            compute='_compute_biometric_sync_state',
                                            help="Whether this employee has reached the biometric readers.")

    @api.depends('barcode', 'biometric_device_ids', 'active')
    def _compute_biometric_sync_state(self):
        device_count = self.env['biometric.config'].search_count([('connection_mode', '=', 'agent')])
        for employee in self:
            linked = len(employee.biometric_device_ids.mapped('device_id'))
            if device_count and linked >= device_count:
                employee.biometric_sync_state = 'synced'
            elif linked:
                employee.biometric_sync_state = 'partial'
            elif employee._usable_badge(employee.barcode):
                employee.biometric_sync_state = 'waiting'
            else:
                employee.biometric_sync_state = 'no_badge'

    @api.model
    def _usable_badge(self, value):
        text = (value or '').strip()
        if not text or not text.isdigit():
            return None
        trimmed = text.lstrip('0') or '0'
        return trimmed if len(trimmed) <= BADGE_DIGIT_LIMIT else None

    def _device_display_name(self):
        self.ensure_one()
        decomposed = unicodedata.normalize('NFKD', self.name or '')
        ascii_only = ''.join(char for char in decomposed if not unicodedata.combining(char))
        cleaned = ''.join(char if char.isalnum() or char == ' ' else ' ' for char in ascii_only)
        return ' '.join(cleaned.upper().split())[:DEVICE_NAME_LIMIT].strip()

    def badge_for_device(self):
        self.ensure_one()
        return self._usable_badge(self.barcode)

    def action_link_to_device_user(self):
        """Open wizard to manually link employee to device user."""
        self.ensure_one()
        return {
            'name': 'Link to Device User',
            'type': 'ir.actions.act_window',
            'res_model': 'link.employee.device.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_employee_id': self.id}
        }


class BiometricAttendanceDevices(models.Model):
    """Model biometric attendance devices and their association with employees."""
    _name = 'biometric.attendance.devices'
    _description = 'biometric attendance devices'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    biometric_attendance_id = fields.Char(string='Biometric User ID', required=True)
    device_id = fields.Many2one('biometric.config', string='Biometric Attendance Device', required=True)
