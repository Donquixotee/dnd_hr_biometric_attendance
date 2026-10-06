# -*- encoding: utf-8 -*-
# This module and its content is copyright of DND Consulting.
# - © DND Consulting 2025. All rights reserved.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Inherits ResConfigSettings to add a configuration parameter
    for minimal attendance in the HR Biometric Attendance module."""
    _inherit = 'res.config.settings'

    minimal_attendance = fields.Boolean(string='Minimal Attendance',
                                        config_parameter='dnd_hr_biometric_attendance.minimal_attendance')
    attendance_pairing_hours = fields.Integer(
        string='Pairing Window (hours)',
        config_parameter='dnd_hr_biometric_attendance.attendance_pairing_hours',
        help="How long after a check in a check out may still close it. Leave at 0 to pair only "
             "within the same calendar day. Set it to cover your longest shift plus any overrun "
             "when people work across midnight.")
