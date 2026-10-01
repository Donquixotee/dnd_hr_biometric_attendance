from odoo.tests.common import TransactionCase


class BiometricCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env['biometric.config'].create({
            'name': 'Main Gate',
            'device_ip': '192.168.1.201',
            'port': 4370,
            'time_zone': 'Africa/Algiers',
            'serialnumber': 'SERIAL-TEST-1',
            'connection_mode': 'agent',
        })
        cls.employee = cls.env['hr.employee'].create({'name': 'Linked Employee'})
        cls.env['biometric.attendance.devices'].create({
            'employee_id': cls.employee.id,
            'biometric_attendance_id': '7',
            'device_id': cls.device.id,
        })

    def logs(self):
        return self.env['attendance.log'].search(
            [('device_id', '=', self.device.id)], order='punching_time')

    @staticmethod
    def punch(user_id, timestamp):
        return {'user_id': user_id, 'timestamp': timestamp}
