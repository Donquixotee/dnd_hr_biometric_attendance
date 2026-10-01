# -*- coding: utf-8 -*-
# This module and its content is copyright of DND Consulting.
# - © DND Consulting 2025. All rights reserved.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class LinkEmployeeDeviceWizard(models.TransientModel):
    """Wizard to manually link employee to a device user."""
    _name = 'link.employee.device.wizard'
    _description = 'Link Employee to Device User Wizard'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, readonly=True)
    device_id = fields.Many2one('biometric.config', string='Biometric Device', required=True)
    device_user_id = fields.Many2one('device.user.cache', string='Device User',
                                     domain="[('device_id', '=', device_id), ('is_linked', '=', False)]",
                                     help="Select a user from the biometric device to link with this employee")
    update_card_number = fields.Boolean(string='Update Employee Card Number', default=True,
                                         help="Update the employee's card number with the device user's card number")

    @api.model
    def default_get(self, fields_list):
        """Override to set employee_id from context."""
        res = super(LinkEmployeeDeviceWizard, self).default_get(fields_list)

        # Get employee from context or active_id
        employee_id = self.env.context.get('default_employee_id') or self.env.context.get('active_id')
        if employee_id:
            res['employee_id'] = employee_id

        return res

    @api.onchange('device_id')
    def _onchange_device_id(self):
        """Reset device_user_id when device changes."""
        self.device_user_id = False

    def action_fetch_device_users(self):
        """Fetch users from device and populate cache - called as button action."""
        self.ensure_one()

        if not self.device_id:
            raise UserError(_("Please select a device first."))

        try:
            # Get device as recordset
            device = self.device_id

            # Clear old cache entries for this device
            self.env['device.user.cache'].search([('device_id', '=', device.id)]).unlink()

            # Fetch users from device
            users = device.get_device_users_for_selection()

            if not users:
                raise UserError(_("No users found on device '%s'.") % device.name)

            # Get already linked user IDs for this device
            linked_user_ids = self.env['biometric.attendance.devices'].search([
                ('device_id', '=', device.id)
            ]).mapped('biometric_attendance_id')

            # Populate cache
            for user in users:
                # Handle card value properly
                card_value = ''
                if user.get('card') not in (None, False, 0, ''):
                    card_value = str(user['card'])

                self.env['device.user.cache'].create({
                    'device_id': device.id,
                    'user_id': user.get('user_id', ''),
                    'name': user.get('name', 'Unknown'),
                    'card': card_value,
                    'uid': user.get('uid', 0),
                    'is_linked': user.get('user_id', '') in linked_user_ids
                })

            _logger.info("Fetched %d users from device %s", len(users), device.name)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Fetched %d users from device "%s". Please select a user below.') % (len(users), device.name),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error("Failed to fetch device users: %s", str(e))
            raise UserError(_("Failed to fetch device users: %s") % str(e))

    def action_link_employee(self):
        """Link the employee to the selected device user."""
        self.ensure_one()

        if not self.device_user_id:
            raise UserError(_("Please select a device user to link."))

        # Check if already linked
        existing_link = self.env['biometric.attendance.devices'].search([
            ('employee_id', '=', self.employee_id.id),
            ('device_id', '=', self.device_id.id)
        ])

        if existing_link:
            raise UserError(_("This employee is already linked to device '%s'. Please remove the existing link first.") % self.device_id.name)

        # Check if device user is already linked to another employee
        device_user_link = self.env['biometric.attendance.devices'].search([
            ('biometric_attendance_id', '=', self.device_user_id.user_id),
            ('device_id', '=', self.device_id.id)
        ])

        if device_user_link:
            raise UserError(_("Device user ID '%s' is already linked to employee '%s'.") % (self.device_user_id.user_id, device_user_link.employee_id.name))

        # Create the link
        self.env['biometric.attendance.devices'].create({
            'employee_id': self.employee_id.id,
            'biometric_attendance_id': self.device_user_id.user_id,
            'device_id': self.device_id.id,
        })

        # Update card number if requested
        if self.update_card_number and self.device_user_id.card:
            self.employee_id.card_number = self.device_user_id.card

        _logger.info("Successfully linked employee '%s' to device user '%s' on device '%s'",
                    self.employee_id.name, self.device_user_id.user_id, self.device_id.name)

        # Show notification and close wizard
        message = _('Employee "%s" has been linked to device user "%s" on device "%s"') % (
            self.employee_id.name, self.device_user_id.name, self.device_id.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Link Successful'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
