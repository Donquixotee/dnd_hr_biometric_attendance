# -*- coding: utf-8 -*-
# This module and its content is copyright of DND Consulting.
# - © DND Consulting 2025. All rights reserved.
# Developer: Amraoui Sofiane

from datetime import datetime
import re
import pytz
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from ..zk import ZK

_logger = logging.getLogger(__name__)

DEVICE_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
PAIRING_HOURS_PARAMETER = 'dnd_hr_biometric_attendance.attendance_pairing_hours'
DEFAULT_CONN_TIMEOUT = 60
CHECK_IN = '0'
CHECK_OUT = '1'


class BiometricDeviceConfig(models.Model):
    """Model to configure and manage biometric devices."""
    _name = 'biometric.config'
    _description = 'biometric config'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _tz_get(self):
        """Return list of timezone tuples for selection field."""
        return [(tz, tz) for tz in sorted(pytz.all_timezones)]

    name = fields.Char(string='Name', required=True)
    device_ip = fields.Char(string='Device IP', required=True)
    port = fields.Integer(string='Port', required=True)
    is_password_set = fields.Boolean(string='Is Password Set', default=False)
    device_password = fields.Char(string='Device Password', null=True, blank=True)
    time_zone = fields.Selection(selection='_tz_get', string='Timezone', default=lambda self: self.env.user.tz or 'GMT')
    location_id = fields.Many2one('hr.work.location', string='Work Location',
                                   help="The physical location where this device is installed (e.g., Building A - Main Entrance)")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, readonly=True)
    connection_mode = fields.Selection([('direct', 'Direct (Odoo reaches the device)'),
                                        ('agent', 'Remote Agent (agent pushes to Odoo)')],
                                       string='Connection Mode', default='direct', required=True,
                                       help="Direct: Odoo connects to the device itself. Use when Odoo is on the same network. "
                                            "Remote Agent: an agent on the device network pushes punches to Odoo. "
                                            "Use when Odoo is hosted externally and cannot reach the device.")
    conn_timeout = fields.Integer(string='Connection Timeout', default=60,
                                  help="Seconds to wait for the device before giving up.")
    force_udp = fields.Boolean(string='Force UDP',
                               help="Skip the TCP attempt and use UDP only. Needed by some older firmwares such as the K40.")
    ommit_ping = fields.Boolean(string='Skip Ping Check',
                                help="Do not ping the device before connecting. Enable when ICMP is blocked by a firewall "
                                     "but the device port is reachable.")
    agent_last_seen = fields.Datetime(string='Agent Last Seen', readonly=True,
                                      help="Last time a remote agent delivered data for this device.")
    punch_direction = fields.Selection([('auto', 'Alternate (single device for in and out)'),
                                        ('in', 'Always Check In'),
                                        ('out', 'Always Check Out')],
                                       string='Punch Direction', default='auto', required=True,
                                       help="Alternate: the device is used for both entering and leaving, so punches "
                                            "alternate check in / check out. Always Check In or Always Check Out: the "
                                            "device guards one direction only, such as separate entrance and exit readers.")

    # Device Information Fields
    firmware_version = fields.Char(string='Firmware Version', readonly=True,
                                   help="The firmware version of the device which will be filled automatically when you get device info.")
    serialnumber = fields.Char(string='Serial Number', readonly=True,
                               help="The serial number of the device which will be filled automatically when you get device info.")
    oem_vendor = fields.Char(string='OEM Vendor', readonly=True,
                               help="The OEM Vendor of the device which will be filled automatically when you get device info.")
    platform = fields.Char(string='Platform', readonly=True,
                               help="The Platform of the device which will be filled automatically when you get device info.")
    fingerprint_algorithm = fields.Char(string='Fingerprint Algorithm', readonly=True,
                               help="The Fingerprint Algorithm (ZKFPVersion) of the device which will be filled automatically when you get device info.")
    device_name = fields.Char(string='Device Model', readonly=True,
                               help="The model of the device which will be filled automatically when you get device info.")
    work_code = fields.Char(string='Work Code', readonly=True,
                               help="The Work Code of the device which will be filled automatically when you get device info.")

    # User Synchronization Fields
    device_users_count = fields.Integer(string='Users in Device', compute='_compute_user_sync_stats', store=False,
                                        help="Total number of users stored in the biometric device")
    users_in_device_not_in_odoo_count = fields.Integer(string='Unmapped Device Users', compute='_compute_user_sync_stats', store=False,
                                                        help="Users in device that are not linked to Odoo employees")
    users_in_odoo_not_in_device_count = fields.Integer(string='Unsynced Odoo Employees', compute='_compute_user_sync_stats', store=False,
                                                        help="Odoo employees not uploaded to this device")
    users_in_device_not_in_odoo_ids = fields.Many2many('biometric.attendance.devices',
                                                        'device_unmapped_users_rel', 'device_id', 'attendance_device_id',
                                                        string='Unmapped Device Users', compute='_compute_user_sync_stats', store=True,
                                                        help="List of device users not linked to employees")
    users_in_odoo_not_in_device_ids = fields.Many2many('hr.employee',
                                                        'device_unsynced_employees_rel', 'device_id', 'employee_id',
                                                        string='Unsynced Employees', compute='_compute_user_sync_stats', store=True,
                                                        help="List of employees not in this device")

    def _compute_user_sync_stats(self):
        """Compute user synchronization statistics."""
        for record in self:
            # Get all biometric device links for this device
            device_links = self.env['biometric.attendance.devices'].search([('device_id', '=', record.id)])

            # Count total users in device (all links)
            record.device_users_count = len(device_links)

            # Users in device not linked to employees (no employee_id)
            unmapped_users = device_links.filtered(lambda d: not d.employee_id)
            record.users_in_device_not_in_odoo_count = len(unmapped_users)
            record.users_in_device_not_in_odoo_ids = [(6, 0, unmapped_users.ids)]

            # Employees in Odoo not in this device
            all_employees = self.env['hr.employee'].search([('company_id', '=', record.company_id.id)])
            employees_in_device = device_links.mapped('employee_id')
            employees_not_in_device = all_employees - employees_in_device
            record.users_in_odoo_not_in_device_count = len(employees_not_in_device)
            record.users_in_odoo_not_in_device_ids = [(6, 0, employees_not_in_device.ids)]

    @api.onchange('is_password_set')
    def on_is_password_set_change(self):
        """Clear the device password if the password field is not set."""
        if not self.is_password_set:
            self.device_password = ''

    @api.onchange('device_password')
    def _check_password(self):
        """Validate the device password."""
        if self.device_password and not self.device_password.isdigit():
            raise UserError(_("Device password should only contain numeric characters."))

    def get_device_info(self):
        """Fetch and store device information from the biometric device."""
        try:
            zk = self._connect_to_device()
            zk.enable_device()

            self.firmware_version = zk.get_firmware_version()
            self.serialnumber = zk.get_serialnumber()
            self.platform = zk.get_platform()
            self.fingerprint_algorithm = zk.get_fp_version()
            self.device_name = zk.get_device_name()
            self.work_code = zk.get_workcode()
            self.oem_vendor = zk.get_oem_vendor()

            zk.disconnect()

            _logger.info("Successfully retrieved device info from %s at %s:%s",
                       self.name, self.device_ip, self.port)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Device Info Retrieved'),
                    'message': _('Device information for "%s" has been updated') % self.name,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error("Failed to get device info from %s at %s:%s - Error: %s",
                        self.name, self.device_ip, self.port, str(e))
            raise UserError(_(str(e)))

    def _ensure_direct_mode(self):
        for device in self:
            if device.connection_mode == 'agent':
                raise UserError(_(
                    'Device "%s" is served by a remote agent. Odoo cannot reach it directly, '
                    'so this operation is unavailable. Run it from the device network, or switch '
                    'the device to Direct mode if Odoo can reach it.') % device.name)

    def test_device_connection(self):
        """Test connection to the biometric device."""
        self._ensure_direct_mode()
        try:
            zk = self._build_zk_client()
            conn = zk.connect()
            if conn:
                zk.disconnect()
                _logger.info("Successfully connected to biometric device %s at %s:%s",
                           self.name, self.device_ip, self.port)

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Successfully connected to device "%s"') % self.name,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise ValidationError(_("Connection Failed"))
        except Exception as e:
            _logger.error("Failed to connect to biometric device %s at %s:%s - Error: %s",
                        self.name, self.device_ip, self.port, str(e))
            raise UserError(_(str(e)))

    def _connect_to_device(self):
        """Establish connection to the biometric device."""
        self._ensure_direct_mode()
        zk = self._build_zk_client()
        conn = zk.connect()
        if not conn:
            raise ValidationError(_("Connection Failed"))
        return zk

    def _import_user_from_device(self, user):
        """Import a single user from device to Odoo.

        Returns: tuple (created_count, updated_count)
        """
        # Check if already linked
        biometric_device = self.env['biometric.attendance.devices'].search([
            ('biometric_attendance_id', '=', user.user_id),
            ('device_id', '=', self.id)
        ])

        if biometric_device:
            return (0, 0)  # Already exists

        employee_name = user.name or f"User {user.user_id}"
        existing_employee = self.env['hr.employee'].search([('name', '=', employee_name)], limit=1)

        if existing_employee:
            # Link existing employee to device
            existing_employee.biometric_device_ids = [(0, 0, {
                'employee_id': existing_employee.id,
                'biometric_attendance_id': user.user_id,
                'device_id': self.id,
            })]
            if user.card:
                existing_employee.card_number = str(user.card)
            return (0, 1)  # Updated
        else:
            # Create new employee
            self.env['hr.employee'].create({
                'name': employee_name,
                'card_number': str(user.card) if user.card else False,
                'biometric_device_ids': [(0, 0, {
                    'biometric_attendance_id': user.user_id,
                    'device_id': self.id,
                })]
            })
            return (1, 0)  # Created

    def sync_employees_from_device(self):
        """Synchronize employees FROM biometric device TO Odoo - imports users from device."""
        try:
            _logger.info("Starting employee import from device %s", self.name)
            zk = self._connect_to_device()
            users = zk.get_users()

            if not users:
                zk.disconnect()
                raise UserError(_("No users found on the device"))

            employees_created = 0
            employees_updated = 0

            for user in users:
                created, updated = self._import_user_from_device(user)
                employees_created += created
                employees_updated += updated

            zk.disconnect()

            _logger.info("Employee import from device %s completed: %s created, %s updated",
                        self.name, employees_created, employees_updated)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import Successful'),
                    'message': _('Imported from device: %s employees created, %s linked to existing employees') % (employees_created, employees_updated),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error("Failed to import employees from device %s - Error: %s", self.name, str(e))
            raise UserError(_(str(e)))

    def _validate_card_number(self, employee):
        """Validate and convert card number to integer.

        Returns: int card value (0 if empty/invalid)
        Raises: UserError if invalid format
        """
        if not employee.card_number:
            return 0
        try:
            return int(employee.card_number)
        except (ValueError, TypeError):
            raise UserError(_(
                "Invalid card number for employee '%s'. Card number must be a valid integer or empty."
            ) % employee.name)

    def _sanitize_employee_name(self, name):
        """Sanitize employee name for device compatibility.

        Returns: str (max 24 chars, stripped)
        """
        return (name or "Unknown").strip()[:24]

    def _get_next_available_ids(self, users):
        """Calculate next available UID and user_id from device users.

        Returns: tuple (next_uid, next_user_id_str, user_id_list_str)
        """
        uid_list = []
        user_id_list = []

        for user in users:
            uid_list.append(user.uid)
            try:
                user_id_list.append(int(user.user_id))
            except (ValueError, TypeError):
                user_id_list.append(user.user_id)

        # Find next UID
        next_uid = uid_list[-1] if uid_list else 0
        uid_list.sort()

        # Find next user_id (numeric only)
        numeric_user_ids = [int(uid) for uid in user_id_list if isinstance(uid, int) or (isinstance(uid, str) and uid.isdigit())]
        if numeric_user_ids:
            numeric_user_ids.sort()
            next_user_id = str(numeric_user_ids[-1] + 1)
        else:
            next_user_id = "1"

        user_id_list_str = [str(uid) for uid in user_id_list]
        return (next_uid, next_user_id, user_id_list_str)

    def _check_device_capacity(self, zk, employees):
        """Check if device has enough capacity for new employees.

        Raises: UserError if capacity exceeded
        """
        zk.read_sizes()
        available_users = zk.users_cap - zk.users
        employees_to_add = len([e for e in employees if not e.biometric_device_ids.filtered(lambda b: b.device_id.id == self.id)])

        if available_users < employees_to_add:
            raise UserError(_(
                "Device capacity exceeded. Available slots: %s, Employees to add: %s. "
                "Device capacity: %s, Current users: %s"
            ) % (available_users, employees_to_add, zk.users_cap, zk.users))

    def _find_user_by_name(self, emp_name, users):
        """Find existing device user by name.

        Returns: User object or None
        """
        for user in users:
            if user.name and user.name.strip()[:24] == emp_name:
                return user
        return None

    def _link_employee_to_existing_user(self, employee, existing_user, zk):
        """Link employee to existing device user and update card if needed."""
        # Create link in Odoo
        employee.biometric_device_ids = [(0, 0, {
            'employee_id': employee.id,
            'biometric_attendance_id': existing_user.user_id,
            'device_id': self.id,
        })]

        # Update card number if provided
        if employee.card_number:
            card_value = self._validate_card_number(employee)
            emp_name = self._sanitize_employee_name(employee.name)
            try:
                zk.set_user(existing_user.uid, emp_name, 0, '', '', str(existing_user.user_id), card=card_value)
            except Exception as e:
                raise UserError(_(
                    "Failed to update card for existing user '%s' (ID: %s, UID: %s). Error: %s"
                ) % (emp_name, existing_user.user_id, existing_user.uid, str(e)))

    def _create_new_user_on_device(self, employee, uid, next_user_id, zk):
        """Create new user on device for employee.

        Returns: str next_user_id (incremented)
        """
        emp_name = self._sanitize_employee_name(employee.name)
        card_value = self._validate_card_number(employee)

        # Create biometric device record in Odoo
        employee.biometric_device_ids = [(0, 0, {
            'employee_id': employee.id,
            'biometric_attendance_id': next_user_id,
            'device_id': self.id,
        })]

        # Add user to device
        try:
            zk.set_user(uid, emp_name, 0, '', '', str(next_user_id), card=card_value)
        except Exception as e:
            raise UserError(_(
                "Failed to set user '%s' (ID: %s, UID: %s) on device. Error: %s"
            ) % (emp_name, next_user_id, uid, str(e)))

        return str(int(next_user_id) + 1)

    def _update_existing_employee_card(self, employee, users, zk):
        """Update card number for employee already linked to device."""
        biometric_device_ids = employee.biometric_device_ids.filtered(lambda b: b.device_id.id == self.id)
        if not biometric_device_ids:
            return

        emp_biometric_attendance_id = biometric_device_ids[0].biometric_attendance_id
        emp_name = self._sanitize_employee_name(employee.name)
        card_value = self._validate_card_number(employee)

        for user in users:
            if user.user_id == emp_biometric_attendance_id:
                try:
                    zk.set_user(user.uid, emp_name, 0, '', '', str(user.user_id), card=card_value)
                except Exception as e:
                    raise UserError(_(
                        "Failed to update user '%s' (ID: %s, UID: %s) on device. Error: %s"
                    ) % (emp_name, user.user_id, user.uid, str(e)))
                break

    def sync_employees(self):
        """Synchronize employees FROM Odoo TO biometric device - uploads Odoo employees to device."""
        employees = self.env['hr.employee'].search([])

        try:
            zk = self._connect_to_device()
            zk.disable_device()

            self._check_device_capacity(zk, employees)
            users = zk.get_users()
            uid, next_user_id, user_id_list_str = self._get_next_available_ids(users)

            # Upload new employees to device
            for employee in employees:
                biometric_device = employee.biometric_device_ids.search(
                    [('employee_id', '=', employee.id), ('device_id', '=', self.id)])

                if not biometric_device:
                    emp_name = self._sanitize_employee_name(employee.name)
                    existing_user = self._find_user_by_name(emp_name, users)

                    if existing_user:
                        # Link to existing device user
                        self._link_employee_to_existing_user(employee, existing_user, zk)
                    else:
                        # Create new user on device
                        uid += 1
                        # Ensure next_user_id is unique
                        while str(next_user_id) in user_id_list_str:
                            next_user_id = str(int(next_user_id) + 1)

                        next_user_id = self._create_new_user_on_device(employee, uid, next_user_id, zk)
                        user_id_list_str.append(str(next_user_id))

            # Update existing employees' card numbers
            for employee in employees:
                biometric_device = employee.biometric_device_ids.search(
                    [('employee_id', '=', employee.id), ('device_id', '=', self.id)])
                if biometric_device:
                    self._update_existing_employee_card(employee, users, zk)

            # Re-enable device after successful sync
            zk.enable_device()
            zk.disconnect()

            _logger.info("Employee upload to device %s completed successfully", self.name)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Upload Successful'),
                    'message': _('All employees have been uploaded to device "%s"') % self.name,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            # Ensure device is re-enabled even if error occurs
            _logger.error("Failed to upload employees to device %s - Error: %s", self.name, str(e))
            try:
                zk.enable_device()
                zk.disconnect()
            except:
                pass  # Ignore errors during cleanup
            raise UserError(_(str(e)))

    def _build_zk_client(self):
        self.ensure_one()
        return ZK(self.device_ip, self.port, password=self.device_password,
                  timeout=self.conn_timeout or DEFAULT_CONN_TIMEOUT,
                  force_udp=self.force_udp, ommit_ping=self.ommit_ping)

    def _has_required_punch_attributes(self, punch):
        for attribute in ('user_id', 'timestamp'):
            if not hasattr(punch, attribute):
                _logger.warning("Skipping punch without '%s' on device %s", attribute, self.name)
                return False
        return True

    def _fetch_punches(self):
        self.ensure_one()
        zk = self._build_zk_client()
        try:
            if not zk.connect():
                raise ValidationError(_('Connection failed to device "%s"') % self.name)
            return [{'user_id': str(punch.user_id),
                     'timestamp': punch.timestamp.strftime(DEVICE_TIME_FORMAT)}
                    for punch in zk.get_attendance() or []
                    if self._has_required_punch_attributes(punch)]
        finally:
            try:
                zk.disconnect()
            except Exception:
                _logger.debug("Could not cleanly disconnect from device %s", self.name)

    def _employee_by_device_user(self):
        self.ensure_one()
        links = self.env['biometric.attendance.devices'].search([('device_id', '=', self.id)])
        employee_by_user = {}
        shared_ids = set()
        for link in links:
            device_user = str(link.biometric_attendance_id)
            if device_user in employee_by_user:
                shared_ids.add(device_user)
            employee_by_user[device_user] = link.employee_id.id
        if shared_ids:
            _logger.warning("Device %s has several employees sharing biometric user ids %s; the last link wins",
                            self.name, sorted(shared_ids))
        return employee_by_user

    def _device_time_to_utc(self, device_timestamp):
        device_tz = pytz.timezone(self.time_zone or 'GMT')
        naive_local = datetime.strptime(device_timestamp, DEVICE_TIME_FORMAT)
        return device_tz.localize(naive_local).astimezone(pytz.utc).replace(tzinfo=None)

    def _already_recorded_keys(self, punching_times):
        if not punching_times:
            return set()
        stored = self.env['attendance.log'].search([('device_id', '=', self.id),
                                                    ('punching_time', 'in', list(punching_times))])
        return {(log.device_user_id, log.punching_time) for log in stored}

    def _latest_status_by_device_user(self, device_users):
        if not device_users:
            return {}
        stored = self.env['attendance.log'].search([('device_id', '=', self.id),
                                                    ('device_user_id', 'in', list(device_users))],
                                                   order='punching_time desc')
        latest = {}
        for log in stored:
            latest.setdefault(log.device_user_id, log.status)
        return latest

    def _fixed_direction_status(self):
        return {'in': CHECK_IN, 'out': CHECK_OUT}.get(self.punch_direction)

    def _prepare_punch_values(self, punches, employee_by_user):
        ordered = sorted(punches, key=lambda punch: (punch['user_id'], punch['punching_time']))
        fixed_status = self._fixed_direction_status()
        last_status = {} if fixed_status else self._latest_status_by_device_user(
            {punch['user_id'] for punch in ordered})
        values = []
        for punch in ordered:
            device_user = punch['user_id']
            status = fixed_status or (CHECK_OUT if last_status.get(device_user) == CHECK_IN else CHECK_IN)
            last_status[device_user] = status
            values.append({'employee_id': employee_by_user[device_user],
                           'punching_time': punch['punching_time'],
                           'status': status,
                           'device': self.name,
                           'device_id': self.id,
                           'device_user_id': device_user,
                           'work_location_id': self.location_id.id,
                           'company_id': self.company_id.id,
                           'is_calculated': False})
        return values

    def process_punches(self, punches):
        self.ensure_one()
        employee_by_user = self._employee_by_device_user()
        unmapped_users = sorted({str(punch['user_id']) for punch in punches
                                 if str(punch['user_id']) not in employee_by_user})
        mapped = [{'user_id': str(punch['user_id']),
                   'punching_time': self._device_time_to_utc(punch['timestamp'])}
                  for punch in punches if str(punch['user_id']) in employee_by_user]
        seen = self._already_recorded_keys({punch['punching_time'] for punch in mapped})
        fresh = []
        for punch in mapped:
            key = (punch['user_id'], punch['punching_time'])
            if key in seen:
                continue
            seen.add(key)
            fresh.append(punch)
        values = self._prepare_punch_values(fresh, employee_by_user)
        if values:
            self.env['attendance.log'].create(values)
        if unmapped_users:
            _logger.warning("Device %s sent punches for users not linked to any employee: %s",
                            self.name, unmapped_users)
        return {'device': self.name,
                'received': len(punches),
                'created': len(values),
                'duplicates': len(mapped) - len(fresh),
                'unmapped_user_ids': unmapped_users}

    def _download_notification(self, title, message, notification_type):
        return {'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': title, 'message': message,
                           'type': notification_type, 'sticky': False}}

    def download_attendance_log(self):
        """Download attendance logs from the biometric device and update or create attendance records."""
        self.ensure_one()
        if self.connection_mode == 'agent':
            return self._download_notification(
                _('Remote Agent Device'),
                _('Device "%s" is served by a remote agent. Odoo does not connect to it directly.') % self.name,
                'warning')
        punches = self._fetch_punches()
        if not punches:
            _logger.warning("No attendance records found on device %s", self.name)
            return self._download_notification(
                _('No Records'),
                _('No attendance records found on device "%s"') % self.name,
                'warning')
        summary = self.process_punches(punches)
        _logger.info("Device %s: %s punches received, %s stored, %s already known",
                     self.name, summary['received'], summary['created'], summary['duplicates'])
        return self._download_notification(
            _('Download Successful'),
            _('Device "%s": %s new punches stored, %s already known.') % (
                self.name, summary['created'], summary['duplicates']),
            'success')

    def _device_by_serial(self, serial_number):
        device = self.search([('serialnumber', '=', serial_number)], limit=1)
        if device:
            device.sudo().write({'agent_last_seen': fields.Datetime.now()})
        return device

    @api.model
    def action_pending_device_users(self, serial_number):
        device = self._device_by_serial(serial_number)
        if not device:
            _logger.warning("Agent asked for pending users of unknown device serial %s", serial_number)
            return {'error': 'unknown_device', 'serial_number': serial_number}
        linked = self.env['biometric.attendance.devices'].search([('device_id', '=', device.id)])
        employees = self.env['hr.employee'].search([('active', '=', True),
                                                    ('id', 'not in', linked.mapped('employee_id').ids),
                                                    ('company_id', '=', device.company_id.id)])
        pending = []
        for employee in employees:
            badge = employee.badge_for_device()
            if not badge:
                _logger.warning("Employee %s has no usable badge, not sent to %s",
                                employee.name, device.name)
                continue
            pending.append({'employee_id': employee.id,
                            'pin': badge,
                            'name': employee._device_display_name()})
        return {'device': device.name, 'pending': pending}

    @api.model
    def action_confirm_device_users(self, serial_number, results):
        device = self._device_by_serial(serial_number)
        if not device:
            return {'error': 'unknown_device', 'serial_number': serial_number}
        Link = self.env['biometric.attendance.devices']
        created = 0
        failed = 0
        for result in results or []:
            if not result.get('ok'):
                failed += 1
                _logger.warning("Device %s refused employee %s: %s", device.name,
                                result.get('employee_id'), result.get('error'))
                continue
            existing = Link.search([('device_id', '=', device.id),
                                    ('employee_id', '=', result['employee_id'])], limit=1)
            values = {'employee_id': result['employee_id'],
                      'biometric_attendance_id': str(result['pin']),
                      'device_id': device.id}
            if existing:
                existing.write(values)
            else:
                Link.create(values)
                created += 1
        return {'device': device.name, 'created': created, 'failed': failed}

    @api.model
    def action_receive_punches(self, serial_number, punches):
        device = self.search([('serialnumber', '=', serial_number)], limit=1)
        if not device:
            _logger.warning("Agent delivered punches for unknown device serial %s", serial_number)
            return {'error': 'unknown_device', 'serial_number': serial_number}
        device.sudo().write({'agent_last_seen': fields.Datetime.now()})
        if not punches:
            return {'device': device.name, 'received': 0, 'created': 0,
                    'duplicates': 0, 'unmapped_user_ids': []}
        try:
            with self.env.cr.savepoint():
                return device.process_punches(punches)
        except Exception as error:
            _logger.exception("Agent punch delivery failed for device %s: %s", device.name, error)
            return {'error': 'processing_failed', 'message': str(error), 'device': device.name}

    def download_attendance_log_new(self):
        """Download attendance logs from all biometric devices."""
        devices = self.env["biometric.config"].search([('connection_mode', '=', 'direct')])
        for device in devices:
            try:
                with self.env.cr.savepoint():
                    device.download_attendance_log()
            except Exception as error:
                _logger.exception("Attendance download failed for device %s: %s", device.name, error)

    def action_view_device_users(self):
        """Open list of all users in this device."""
        self.ensure_one()
        device_links = self.env['biometric.attendance.devices'].search([('device_id', '=', self.id)])

        return {
            'name': _('Device Users'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.attendance.devices',
            'view_mode': 'list,form',
            'domain': [('id', 'in', device_links.ids)],
            'context': {'default_device_id': self.id}
        }

    def action_view_unmapped_users(self):
        """Open list of device users not linked to Odoo employees."""
        self.ensure_one()

        return {
            'name': _('Unmapped Device Users'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.attendance.devices',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.users_in_device_not_in_odoo_ids.ids)],
            'context': {'default_device_id': self.id}
        }

    def action_view_unsynced_employees(self):
        """Open list of Odoo employees not in this device."""
        self.ensure_one()

        return {
            'name': _('Employees Not in Device'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.users_in_odoo_not_in_device_ids.ids)],
        }

    def get_device_users_for_selection(self):
        """Fetch all users from device for manual selection.

        Returns: list of tuples [(user_id, name, card), ...]
        """
        try:
            zk = self._connect_to_device()
            users = zk.get_users()
            zk.disconnect()

            # Return list of user data as tuples
            user_list = []
            for user in users:
                user_list.append({
                    'user_id': user.user_id,
                    'name': user.name or f"User {user.user_id}",
                    'card': user.card or 0,
                    'uid': user.uid
                })
            return user_list
        except Exception as e:
            _logger.error("Failed to fetch users from device %s - Error: %s", self.name, str(e))
            raise UserError(_(str(e)))
