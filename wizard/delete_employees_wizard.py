# -*- coding: utf-8 -*-
# This module and its content is copyright of DND Consulting.
# - © DND Consulting 2025. All rights reserved.
# Developer: Amraoui Sofiane

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from ..zk import ZK

_logger = logging.getLogger(__name__)


class DeleteEmployeesWizard(models.TransientModel):
    """Wizard for deleting multiple employees from biometric device."""
    _name = 'delete.employees.wizard'
    _description = 'Delete Employees from Device Wizard'

    device_id = fields.Many2one('biometric.config', string='Biometric Device', required=True)
    device_name = fields.Char(related='device_id.name', string='Device Name', readonly=True)
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Employees to Delete',
        required=True,
        help='Select employees to delete from the biometric device'
    )
    delete_from_odoo = fields.Boolean(
        string='Also Delete Link from Odoo',
        default=True,
        help='If checked, will also remove the biometric device link from employee records in Odoo'
    )

    @api.model
    def default_get(self, fields_list):
        """Set default device and employees from context."""
        res = super(DeleteEmployeesWizard, self).default_get(fields_list)

        # Get device from context
        device_id = self._context.get('default_device_id') or self._context.get('active_id')
        if device_id and self._context.get('active_model') == 'biometric.config':
            res['device_id'] = device_id

        # Get employees if called from employee list view
        if self._context.get('active_model') == 'hr.employee':
            active_ids = self._context.get('active_ids', [])
            if active_ids:
                res['employee_ids'] = [(6, 0, active_ids)]

        return res

    def _validate_employees_on_device(self, zk, employees):
        """Validate which employees exist on device and return valid ones.

        Returns: tuple (valid_employees, not_found_employees)
        """
        users = zk.get_users()
        if not users:
            raise UserError(_("No users found on the device"))

        device_user_ids = {user.user_id for user in users}
        valid_employees = []
        not_found_employees = []

        for employee in employees:
            # Get biometric ID for this device
            biometric_device = employee.biometric_device_ids.filtered(
                lambda b: b.device_id.id == self.device_id.id
            )

            if not biometric_device:
                not_found_employees.append(employee.name)
                continue

            biometric_id = biometric_device[0].biometric_attendance_id

            if biometric_id in device_user_ids:
                valid_employees.append((employee, biometric_id, biometric_device[0]))
            else:
                not_found_employees.append(employee.name)

        return valid_employees, not_found_employees

    def delete_employees_from_device(self):
        """Delete selected employees from the biometric device."""
        self.ensure_one()

        if not self.employee_ids:
            raise UserError(_("Please select at least one employee to delete."))

        device = self.device_id
        employees = self.employee_ids

        try:
            _logger.info("Starting deletion of %s employees from device %s",
                        len(employees), device.name)

            # Connect to device
            device._ensure_direct_mode()
            zk = ZK(device.device_ip, device.port, password=device.device_password)
            conn = zk.connect()

            if not conn:
                raise ValidationError(_("Connection to device failed"))

            zk.disable_device()  # Lock device during deletion

            # Validate employees on device
            valid_employees, not_found = self._validate_employees_on_device(zk, employees)

            if not valid_employees and not_found:
                zk.enable_device()
                zk.disconnect()
                raise UserError(_(
                    "None of the selected employees are found on device '%s'.\n"
                    "Employees not found: %s"
                ) % (device.name, ', '.join(not_found)))

            # Delete employees from device
            deleted_count = 0
            failed_deletions = []

            for employee, biometric_id, biometric_record in valid_employees:
                try:
                    # Delete from device
                    zk.delete_user(user_id=str(biometric_id))

                    # Delete link from Odoo if requested
                    if self.delete_from_odoo:
                        biometric_record.unlink()

                    deleted_count += 1
                    _logger.info("Deleted employee %s (ID: %s) from device %s",
                               employee.name, biometric_id, device.name)

                except Exception as e:
                    failed_deletions.append(f"{employee.name} (ID: {biometric_id})")
                    _logger.error("Failed to delete employee %s from device %s - Error: %s",
                                employee.name, device.name, str(e))

            # Re-enable device
            zk.enable_device()
            zk.disconnect()

            # Prepare result message
            message_parts = []

            if deleted_count > 0:
                message_parts.append(
                    _('%s employee(s) successfully deleted from device') % deleted_count
                )

            if failed_deletions:
                message_parts.append(
                    _('Failed to delete: %s') % ', '.join(failed_deletions)
                )

            if not_found:
                message_parts.append(
                    _('Not found on device: %s') % ', '.join(not_found)
                )

            # Determine notification type
            if deleted_count > 0 and not failed_deletions:
                notification_type = 'success'
                title = _('Deletion Successful')
            elif deleted_count > 0 and failed_deletions:
                notification_type = 'warning'
                title = _('Partial Success')
            else:
                notification_type = 'danger'
                title = _('Deletion Failed')

            _logger.info("Deletion completed for device %s: %s deleted, %s failed, %s not found",
                        device.name, deleted_count, len(failed_deletions), len(not_found))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': title,
                    'message': '\n'.join(message_parts),
                    'type': notification_type,
                    'sticky': True if failed_deletions or not_found else False,
                }
            }

        except Exception as e:
            _logger.error("Failed to delete employees from device %s - Error: %s",
                        device.name, str(e))
            try:
                zk.enable_device()
                zk.disconnect()
            except:
                pass
            raise UserError(_(str(e)))
