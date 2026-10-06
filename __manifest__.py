# -*- coding: utf-8 -*-
# This module and its content is copyright of DND Consulting.
# - © DND Consulting 2025. All rights reserved.


{
    'name': 'ZKteco Biometric Attendance Integration',
    'version': '17.0.1.0',
    'category': 'Human Resources',
    'sequence': 1,
    'author': 'DND Consulting - Amraoui Sofiane',
    'summary': 'Advanced integration of ZKteco biometric devices with Odoo for accurate employee attendance tracking.',
    'website': 'https://www.dndconsulting.dz/',
    'license': 'LGPL-3',
    'description': """
        ZKteco Biometric Attendance Integration
        ========================================

        Features:
        ---------
        * Bidirectional employee synchronization (Odoo ↔ Device)
        * Intelligent duplicate detection by name
        * Automatic card number management
        * Real-time attendance log download
        * Timezone conversion support
        * Multi-device support
        * Comprehensive logging
        * Clean notification system

        Developed by: Amraoui Sofiane
        Company: DND Consulting
    """,
    'depends': ['hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/biometric_data.xml',
        'wizard/attendance_calc_wizard_view.xml',
        'wizard/biometric_device_view.xml',
        'wizard/attendance_report_wizard_view.xml',
        'wizard/delete_employees_wizard_view.xml',
        'wizard/link_employee_device_wizard_view.xml',
        'views/biometric_device_config_view.xml',
        'views/biometric_attendance_devices_view.xml',
        'views/attendance_log_view.xml',
        'views/hr_attendance_view.xml',
        'views/hr_employee_view.xml',
        'views/res_config_settings.xml',
        'views/menu.xml',

    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'maintainer': 'Amraoui Sofiane <s.amraoui@dndconsulting.dz>',
}
