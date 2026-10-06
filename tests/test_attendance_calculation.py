from odoo.tests.common import tagged

from .common import BiometricCase


@tagged('post_install', '-at_install')
class TestAttendanceCalculation(BiometricCase):

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(
            'dnd_hr_biometric_attendance.minimal_attendance', '')

    def calculate(self):
        self.env['attendance.calc.wizard'].calculate_attendance()

    def attendances(self):
        return self.env['hr.attendance'].search(
            [('employee_id', '=', self.employee.id)], order='check_in')

    def test_a_punch_pair_becomes_one_attendance(self):
        self.device.process_punches([
            self.punch('7', '2026-09-10 08:00:00'),
            self.punch('7', '2026-09-10 17:00:00'),
        ])
        self.calculate()
        attendance = self.attendances()
        self.assertEqual(len(attendance), 1)
        self.assertEqual(str(attendance.check_in), '2026-09-10 07:00:00')
        self.assertEqual(str(attendance.check_out), '2026-09-10 16:00:00')

    def test_processed_logs_are_marked_calculated(self):
        self.device.process_punches([
            self.punch('7', '2026-09-10 08:00:00'),
            self.punch('7', '2026-09-10 17:00:00'),
        ])
        self.calculate()
        self.assertTrue(all(self.logs().mapped('is_calculated')))

    def test_an_unpaired_punch_leaves_attendance_open(self):
        self.device.process_punches([self.punch('7', '2026-09-10 08:00:00')])
        self.calculate()
        self.assertFalse(self.attendances().check_out)

    def _force_two_open_attendances(self):
        attendances = self.env['hr.attendance'].create([
            {'employee_id': self.employee.id,
             'check_in': '2026-09-08 07:00:00', 'check_out': '2026-09-08 15:00:00'},
            {'employee_id': self.employee.id,
             'check_in': '2026-09-09 07:00:00', 'check_out': '2026-09-09 15:00:00'},
        ])
        self.env.cr.execute(
            "UPDATE hr_attendance SET check_out = NULL WHERE id IN %s",
            (tuple(attendances.ids),))
        attendances.invalidate_recordset()
        return attendances

    def test_several_open_attendances_do_not_raise(self):
        self._force_two_open_attendances()
        self.device.process_punches([self.punch('7', '2026-09-10 17:00:00')])
        self.calculate()
        self.assertTrue(all(self.logs().mapped('is_calculated')))

    def test_open_attendances_from_earlier_days_are_closed_on_their_own_day(self):
        self._force_two_open_attendances()
        self.device.process_punches([self.punch('7', '2026-09-10 08:00:00')])
        self.calculate()
        earlier = self.env['hr.attendance'].search(
            [('employee_id', '=', self.employee.id), ('check_in', '<', '2026-09-10')])
        self.assertTrue(all(attendance.check_out for attendance in earlier))
        for attendance in earlier:
            self.assertEqual(attendance.check_in.date(), attendance.check_out.date())

    def test_calculating_twice_does_not_duplicate_attendance(self):
        self.device.process_punches([
            self.punch('7', '2026-09-10 08:00:00'),
            self.punch('7', '2026-09-10 17:00:00'),
        ])
        self.calculate()
        self.calculate()
        self.assertEqual(len(self.attendances()), 1)


@tagged('post_install', '-at_install')
class TestSameDayPairing(BiometricCase):

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(
            'dnd_hr_biometric_attendance.minimal_attendance', '')
        self.exit_device = self.env['biometric.config'].create({
            'name': 'Exit', 'device_ip': '192.168.1.200', 'port': 4370,
            'time_zone': 'Africa/Algiers', 'serialnumber': 'SERIAL-EXIT',
            'connection_mode': 'agent', 'punch_direction': 'out'})
        self.env['biometric.attendance.devices'].create({
            'employee_id': self.employee.id, 'biometric_attendance_id': '7',
            'device_id': self.exit_device.id})
        self.device.punch_direction = 'in'

    def calculate(self):
        self.env['attendance.calc.wizard'].calculate_attendance()

    def attendances(self):
        return self.env['hr.attendance'].search(
            [('employee_id', '=', self.employee.id)], order='check_in')

    def test_check_out_does_not_close_an_attendance_from_months_ago(self):
        stale = self.env['hr.attendance'].create({
            'employee_id': self.employee.id, 'check_in': '2026-05-11 12:43:26'})
        self.exit_device.process_punches([self.punch('7', '2026-09-01 13:30:17')])
        self.calculate()
        self.assertFalse(stale.check_out)

    def test_orphan_check_out_creates_no_attendance(self):
        self.exit_device.process_punches([self.punch('7', '2026-09-01 13:30:17')])
        self.calculate()
        self.assertFalse(self.attendances())

    def test_same_day_pair_still_works(self):
        self.device.process_punches([self.punch('7', '2026-09-01 08:00:00')])
        self.exit_device.process_punches([self.punch('7', '2026-09-01 17:00:00')])
        self.calculate()
        attendance = self.attendances()
        self.assertEqual(len(attendance), 1)
        self.assertTrue(attendance.check_out)

    def test_second_check_in_does_not_open_a_duplicate(self):
        self.device.process_punches([self.punch('7', '2026-09-01 08:00:00'),
                                     self.punch('7', '2026-09-01 08:00:30')])
        self.calculate()
        self.assertEqual(len(self.attendances()), 1)

    def test_check_out_before_check_in_leaves_one_open_attendance(self):
        self.exit_device.process_punches([self.punch('7', '2026-09-01 13:30:17')])
        self.device.process_punches([self.punch('7', '2026-09-01 13:31:34')])
        self.calculate()
        attendance = self.attendances()
        self.assertEqual(len(attendance), 1)
        self.assertEqual(str(attendance.check_in), '2026-09-01 12:31:34')
        self.assertFalse(attendance.check_out)

    def test_late_evening_shift_pairs_within_the_local_day(self):
        self.device.process_punches([self.punch('7', '2026-09-01 22:00:00')])
        self.exit_device.process_punches([self.punch('7', '2026-09-01 23:30:00')])
        self.calculate()
        self.assertTrue(self.attendances().check_out)

    def test_shift_crossing_midnight_does_not_pair(self):
        self.device.process_punches([self.punch('7', '2026-09-01 22:00:00')])
        self.exit_device.process_punches([self.punch('7', '2026-09-02 06:00:00')])
        self.calculate()
        self.assertFalse(self.attendances().check_out)

    def test_check_in_succeeds_even_with_a_stale_open_attendance(self):
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id, 'check_in': '2026-05-11 12:43:26'})
        self.device.process_punches([self.punch('7', '2026-09-01 08:00:00')])
        self.calculate()
        stale = self.env['hr.attendance'].search(
            [('employee_id', '=', self.employee.id), ('check_in', '<', '2026-09-01')])
        self.assertTrue(stale.check_out)
        self.assertEqual(stale.check_out.date(), stale.check_in.date())
        self.assertTrue(all(self.logs().mapped('is_calculated')))


@tagged('post_install', '-at_install')
class TestPairingWindow(BiometricCase):

    def setUp(self):
        super().setUp()
        parameters = self.env['ir.config_parameter'].sudo()
        parameters.set_param('dnd_hr_biometric_attendance.minimal_attendance', '')
        self.exit_device = self.env['biometric.config'].create({
            'name': 'Exit', 'device_ip': '192.168.1.200', 'port': 4370,
            'time_zone': 'Africa/Algiers', 'serialnumber': 'SERIAL-WINDOW',
            'connection_mode': 'agent', 'punch_direction': 'out'})
        self.env['biometric.attendance.devices'].create({
            'employee_id': self.employee.id, 'biometric_attendance_id': '7',
            'device_id': self.exit_device.id})
        self.device.punch_direction = 'in'

    def set_window(self, hours):
        self.env['ir.config_parameter'].sudo().set_param(
            'dnd_hr_biometric_attendance.attendance_pairing_hours', str(hours))

    def calculate(self):
        self.env['attendance.calc.wizard'].calculate_attendance()

    def attendance(self):
        return self.env['hr.attendance'].search(
            [('employee_id', '=', self.employee.id)], order='check_in')

    def work(self, check_in, check_out):
        self.device.process_punches([self.punch('7', check_in)])
        self.exit_device.process_punches([self.punch('7', check_out)])
        self.calculate()

    def test_evening_shift_ending_before_midnight_pairs_with_no_window(self):
        self.set_window(0)
        self.work('2026-09-01 15:30:00', '2026-09-01 23:30:00')
        self.assertTrue(self.attendance().check_out)

    def test_overrunning_past_midnight_is_lost_with_no_window(self):
        self.set_window(0)
        self.work('2026-09-01 15:30:00', '2026-09-02 00:15:00')
        self.assertFalse(self.attendance().check_out)

    def test_a_window_rescues_the_overrun(self):
        self.set_window(12)
        self.work('2026-09-01 15:30:00', '2026-09-02 00:15:00')
        self.assertTrue(self.attendance().check_out)

    def test_a_true_night_shift_pairs_within_the_window(self):
        self.set_window(12)
        self.work('2026-09-01 23:30:00', '2026-09-02 07:30:00')
        attendance = self.attendance()
        self.assertEqual(len(attendance), 1)
        self.assertTrue(attendance.check_out)

    def test_the_window_still_refuses_something_far_older(self):
        self.set_window(12)
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id, 'check_in': '2026-05-11 12:43:26'})
        self.exit_device.process_punches([self.punch('7', '2026-09-01 17:00:00')])
        self.calculate()
        stale = self.env['hr.attendance'].search(
            [('employee_id', '=', self.employee.id), ('check_in', '<', '2026-09-01')])
        self.assertNotEqual(stale.check_out and stale.check_out.date().isoformat(), '2026-09-01')

    def test_day_shift_is_unaffected_either_way(self):
        for hours in (0, 12):
            self.set_window(hours)
            self.env['hr.attendance'].search([('employee_id', '=', self.employee.id)]).unlink()
            self.env['attendance.log'].search([]).write({'is_calculated': False})
            self.env['attendance.log'].search([]).unlink()
            self.work('2026-09-01 07:30:00', '2026-09-01 15:30:00')
            self.assertTrue(self.attendance().check_out, 'failed with window=%s' % hours)
