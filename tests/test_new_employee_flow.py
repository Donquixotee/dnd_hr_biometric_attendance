from odoo.tests.common import tagged

from .common import BiometricCase


@tagged('post_install', '-at_install')
class TestAutomaticBadge(BiometricCase):

    def test_badge_is_never_invented_for_a_new_employee(self):
        employee = self.env['hr.employee'].create({'name': 'NEW HIRE'})
        self.assertFalse(employee.barcode)

    def test_a_supplied_badge_is_kept(self):
        employee = self.env['hr.employee'].create({'name': 'WITH BADGE', 'barcode': '4242'})
        self.assertEqual(employee.barcode, '4242')

    def test_employee_without_a_badge_is_flagged(self):
        employee = self.env['hr.employee'].create({'name': 'NO BADGE'})
        self.assertEqual(employee.biometric_sync_state, 'no_badge')

    def test_employee_with_a_badge_is_waiting(self):
        employee = self.env['hr.employee'].create({'name': 'READY', 'barcode': '4243'})
        self.assertEqual(employee.biometric_sync_state, 'waiting')

    def test_linked_employee_shows_as_synced(self):
        self.assertEqual(self.employee.biometric_sync_state, 'synced')

    def test_device_name_is_transliterated_and_truncated(self):
        employee = self.env['hr.employee'].create({'name': 'Benaïssa Réda El-Hadj Mohammed Lamine'})
        display = employee._device_display_name()
        self.assertEqual(display, display.upper())
        self.assertLessEqual(len(display), 24)
        self.assertNotIn('Ï', display)


@tagged('post_install', '-at_install')
class TestPendingDeviceUsers(BiometricCase):

    def pending(self):
        return self.env['biometric.config'].action_pending_device_users('SERIAL-TEST-1')

    def test_a_new_employee_with_a_badge_appears_as_pending(self):
        employee = self.env['hr.employee'].create({'name': 'BRAND NEW', 'barcode': '5001'})
        pending = self.pending()['pending']
        self.assertIn(employee.id, [item['employee_id'] for item in pending])

    def test_an_employee_without_a_badge_is_never_sent(self):
        employee = self.env['hr.employee'].create({'name': 'NO BADGE YET'})
        pending = self.pending()['pending']
        self.assertNotIn(employee.id, [item['employee_id'] for item in pending])

    def test_filling_the_badge_makes_them_pending(self):
        employee = self.env['hr.employee'].create({'name': 'LATE BADGE'})
        self.assertNotIn(employee.id, [item['employee_id'] for item in self.pending()['pending']])
        employee.barcode = '5002'
        self.assertIn(employee.id, [item['employee_id'] for item in self.pending()['pending']])

    def test_an_already_linked_employee_is_not_pending(self):
        pending = self.pending()['pending']
        self.assertNotIn(self.employee.id, [item['employee_id'] for item in pending])

    def test_archived_employees_are_not_pending(self):
        employee = self.env['hr.employee'].create({'name': 'LEAVER', 'barcode': '5003'})
        employee.active = False
        pending = self.pending()['pending']
        self.assertNotIn(employee.id, [item['employee_id'] for item in pending])

    def test_unknown_serial_returns_an_error(self):
        response = self.env['biometric.config'].action_pending_device_users('NOPE')
        self.assertEqual(response['error'], 'unknown_device')

    def test_asking_stamps_the_heartbeat(self):
        self.device.agent_last_seen = False
        self.pending()
        self.assertTrue(self.device.agent_last_seen)

    def test_confirming_creates_the_link(self):
        employee = self.env['hr.employee'].create({'name': 'TO LINK', 'barcode': '5004'})
        badge = employee.badge_for_device()
        response = self.env['biometric.config'].action_confirm_device_users(
            'SERIAL-TEST-1', [{'employee_id': employee.id, 'pin': badge, 'uid': 42, 'ok': True}])
        self.assertEqual(response['created'], 1)
        link = self.env['biometric.attendance.devices'].search(
            [('device_id', '=', self.device.id), ('employee_id', '=', employee.id)])
        self.assertEqual(link.biometric_attendance_id, badge)

    def test_a_failed_write_creates_no_link(self):
        employee = self.env['hr.employee'].create({'name': 'FAILED ONE', 'barcode': '5005'})
        response = self.env['biometric.config'].action_confirm_device_users(
            'SERIAL-TEST-1', [{'employee_id': employee.id, 'pin': '1', 'ok': False, 'error': 'refused'}])
        self.assertEqual(response['created'], 0)
        self.assertEqual(response['failed'], 1)
        self.assertFalse(self.env['biometric.attendance.devices'].search(
            [('device_id', '=', self.device.id), ('employee_id', '=', employee.id)]))

    def test_confirming_twice_does_not_duplicate_the_link(self):
        employee = self.env['hr.employee'].create({'name': 'TWICE', 'barcode': '5006'})
        badge = employee.badge_for_device()
        payload = [{'employee_id': employee.id, 'pin': badge, 'uid': 9, 'ok': True}]
        self.env['biometric.config'].action_confirm_device_users('SERIAL-TEST-1', payload)
        self.env['biometric.config'].action_confirm_device_users('SERIAL-TEST-1', payload)
        links = self.env['biometric.attendance.devices'].search(
            [('device_id', '=', self.device.id), ('employee_id', '=', employee.id)])
        self.assertEqual(len(links), 1)

    def test_pending_then_confirm_removes_them_from_pending(self):
        employee = self.env['hr.employee'].create({'name': 'CYCLE', 'barcode': '5007'})
        pending = self.pending()['pending']
        entry = next(item for item in pending if item['employee_id'] == employee.id)
        self.env['biometric.config'].action_confirm_device_users(
            'SERIAL-TEST-1', [{'employee_id': entry['employee_id'], 'pin': entry['pin'], 'ok': True}])
        self.assertNotIn(employee.id, [item['employee_id'] for item in self.pending()['pending']])
