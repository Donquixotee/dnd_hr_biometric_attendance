import base64

from odoo.tests.common import tagged

from .common import BiometricCase


@tagged('post_install', '-at_install')
class TestAttendanceReport(BiometricCase):

    def wizard(self, report_from):
        return self.env['attendance.report.wizard'].create({
            'report_from': report_from,
            'date_from': '2026-09-01 00:00:00',
            'date_to': '2026-09-02 00:59:59'})

    def punch_a_day(self):
        self.device.punch_direction = 'auto'
        self.device.process_punches([self.punch('7', '2026-09-01 08:00:00'),
                                     self.punch('7', '2026-09-01 17:00:00')])
        self.env['attendance.calc.wizard'].calculate_attendance()

    def test_exporting_from_attendance_produces_a_file(self):
        self.punch_a_day()
        wizard = self.wizard('attend')
        wizard.export_attendance_xlsx()
        self.assertTrue(wizard.is_printed)
        self.assertTrue(wizard.report_file)
        self.assertTrue(wizard.report_name.endswith('.xlsx'))

    def test_exporting_from_logs_produces_a_file(self):
        self.punch_a_day()
        wizard = self.wizard('log')
        wizard.export_attendance_xlsx()
        self.assertTrue(wizard.is_printed)
        self.assertTrue(wizard.report_file)

    def test_the_file_is_a_real_xlsx(self):
        self.punch_a_day()
        wizard = self.wizard('attend')
        wizard.export_attendance_xlsx()
        content = base64.b64decode(wizard.report_file)
        self.assertEqual(content[:2], b'PK')

    def test_exporting_with_no_data_still_works(self):
        wizard = self.wizard('attend')
        wizard.export_attendance_xlsx()
        self.assertTrue(wizard.is_printed)

    def test_the_action_returned_reopens_the_wizard(self):
        self.punch_a_day()
        wizard = self.wizard('attend')
        action = wizard.export_attendance_xlsx()
        self.assertEqual(action['res_model'], 'attendance.report.wizard')
        self.assertEqual(action['res_id'], wizard.id)
        self.assertIn('report_file', action['context'])

    def test_going_back_clears_the_printed_flag(self):
        wizard = self.wizard('attend')
        wizard.export_attendance_xlsx()
        wizard.action_back()
        self.assertFalse(wizard.is_printed)
