from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import BiometricCase


@tagged('post_install', '-at_install')
class TestPunchProcessing(BiometricCase):

    def test_maps_punches_to_linked_employee(self):
        summary = self.device.process_punches([self.punch('7', '2026-09-10 08:00:00')])
        self.assertEqual(summary['created'], 1)
        self.assertEqual(self.logs().employee_id, self.employee)

    def test_converts_device_time_to_utc(self):
        self.device.process_punches([self.punch('7', '2026-09-10 08:00:00')])
        self.assertEqual(str(self.logs().punching_time), '2026-09-10 07:00:00')

    def test_alternates_check_in_and_check_out(self):
        self.device.process_punches([
            self.punch('7', '2026-09-10 08:00:00'),
            self.punch('7', '2026-09-10 17:00:00'),
        ])
        self.assertEqual(self.logs().mapped('status'), ['0', '1'])

    def test_direction_continues_across_separate_deliveries(self):
        self.device.process_punches([self.punch('7', '2026-09-10 08:00:00')])
        self.device.process_punches([self.punch('7', '2026-09-10 17:00:00')])
        self.assertEqual(self.logs().mapped('status'), ['0', '1'])

    def test_replaying_a_delivery_creates_nothing(self):
        punches = [self.punch('7', '2026-09-10 08:00:00'),
                   self.punch('7', '2026-09-10 17:00:00')]
        self.device.process_punches(punches)
        summary = self.device.process_punches(punches)
        self.assertEqual(summary['created'], 0)
        self.assertEqual(summary['duplicates'], 2)
        self.assertEqual(len(self.logs()), 2)

    def test_duplicate_timestamps_within_one_batch_are_collapsed(self):
        summary = self.device.process_punches([
            self.punch('7', '2026-09-10 08:00:00'),
            self.punch('7', '2026-09-10 08:00:00'),
        ])
        self.assertEqual(summary['created'], 1)
        self.assertEqual(summary['duplicates'], 1)

    def test_unmapped_user_is_reported_and_not_recorded(self):
        summary = self.device.process_punches([self.punch('99', '2026-09-10 08:00:00')])
        self.assertEqual(summary['created'], 0)
        self.assertEqual(summary['unmapped_user_ids'], ['99'])
        self.assertFalse(self.logs())

    def test_numeric_user_id_matches_the_string_link(self):
        summary = self.device.process_punches([self.punch(7, '2026-09-10 08:00:00')])
        self.assertEqual(summary['created'], 1)

    def test_empty_delivery_is_harmless(self):
        self.assertEqual(self.device.process_punches([])['created'], 0)

    def test_punches_are_stamped_with_their_device(self):
        self.device.process_punches([self.punch('7', '2026-09-10 08:00:00')])
        self.assertEqual(self.logs().device_id, self.device)
        self.assertEqual(self.logs().device_user_id, '7')


@tagged('post_install', '-at_install')
class TestAgentEntrypoint(BiometricCase):

    def receive(self, punches):
        return self.env['biometric.config'].action_receive_punches('SERIAL-TEST-1', punches)

    def test_delivers_punches_for_a_known_serial(self):
        self.assertEqual(self.receive([self.punch('7', '2026-09-10 08:00:00')])['created'], 1)

    def test_unknown_serial_returns_an_error_instead_of_raising(self):
        response = self.env['biometric.config'].action_receive_punches('NO-SUCH-SERIAL', [])
        self.assertEqual(response['error'], 'unknown_device')

    def test_delivery_stamps_the_heartbeat(self):
        self.assertFalse(self.device.agent_last_seen)
        self.receive([self.punch('7', '2026-09-10 08:00:00')])
        self.assertTrue(self.device.agent_last_seen)

    def test_empty_delivery_still_stamps_the_heartbeat(self):
        self.receive([])
        self.assertTrue(self.device.agent_last_seen)


@tagged('post_install', '-at_install')
class TestAgentModeGuards(BiometricCase):

    def test_write_operations_are_blocked_in_agent_mode(self):
        for operation in (self.device.test_device_connection,
                          self.device.get_device_info,
                          self.device.sync_employees_from_device,
                          self.device.sync_employees,
                          self.device.get_device_users_for_selection):
            with self.assertRaises(UserError):
                operation()

    def test_download_is_skipped_rather_than_attempted(self):
        notification = self.device.download_attendance_log()
        self.assertEqual(notification['params']['type'], 'warning')

    def test_cron_ignores_agent_devices(self):
        self.env['biometric.config'].download_attendance_log_new()
        self.assertFalse(self.logs())

    def test_direct_mode_allows_write_operations_to_proceed(self):
        self.device.connection_mode = 'direct'
        self.device.ommit_ping = True
        self.device.conn_timeout = 1
        with self.assertRaises(UserError) as caught:
            self.device.test_device_connection()
        self.assertNotIn('remote agent', str(caught.exception))


@tagged('post_install', '-at_install')
class TestDedicatedDirectionReaders(BiometricCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device.write({'name': 'Entrance', 'punch_direction': 'in'})
        cls.exit_device = cls.env['biometric.config'].create({
            'name': 'Exit',
            'device_ip': '192.168.1.200',
            'port': 4370,
            'time_zone': 'Africa/Algiers',
            'serialnumber': 'SERIAL-TEST-2',
            'connection_mode': 'agent',
            'punch_direction': 'out',
        })
        cls.env['biometric.attendance.devices'].create({
            'employee_id': cls.employee.id,
            'biometric_attendance_id': '7',
            'device_id': cls.exit_device.id,
        })

    def test_entrance_reader_marks_every_punch_as_check_in(self):
        self.device.process_punches([
            self.punch('7', '2026-09-10 08:00:00'),
            self.punch('7', '2026-09-11 08:00:00'),
            self.punch('7', '2026-09-12 08:00:00'),
        ])
        self.assertEqual(self.logs().mapped('status'), ['0', '0', '0'])

    def test_exit_reader_marks_every_punch_as_check_out(self):
        self.exit_device.process_punches([
            self.punch('7', '2026-09-10 17:00:00'),
            self.punch('7', '2026-09-11 17:00:00'),
        ])
        logs = self.env['attendance.log'].search(
            [('device_id', '=', self.exit_device.id)], order='punching_time')
        self.assertEqual(logs.mapped('status'), ['1', '1'])

    def test_two_readers_produce_a_usable_day(self):
        self.device.process_punches([self.punch('7', '2026-09-10 08:00:00')])
        self.exit_device.process_punches([self.punch('7', '2026-09-10 17:00:00')])
        logs = self.env['attendance.log'].search(
            [('employee_id', '=', self.employee.id)], order='punching_time')
        self.assertEqual(logs.mapped('status'), ['0', '1'])

    def test_same_person_scanned_twice_at_entrance_stays_check_in(self):
        self.device.process_punches([
            self.punch('7', '2026-09-10 08:00:00'),
            self.punch('7', '2026-09-10 08:00:30'),
        ])
        self.assertEqual(self.logs().mapped('status'), ['0', '0'])

    def test_alternate_mode_is_unchanged_for_single_device_sites(self):
        self.device.punch_direction = 'auto'
        self.device.process_punches([
            self.punch('7', '2026-09-10 08:00:00'),
            self.punch('7', '2026-09-10 17:00:00'),
        ])
        self.assertEqual(self.logs().mapped('status'), ['0', '1'])
