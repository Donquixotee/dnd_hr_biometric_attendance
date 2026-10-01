# -*- coding: utf-8 -*-
# This module and its content is copyright of DND Consulting.
# - © DND Consulting 2025. All rights reserved.

from datetime import datetime, timedelta
import logging

import pytz

from odoo import models

_logger = logging.getLogger(__name__)

CHECK_IN = '0'
CHECK_OUT = '1'


class AttendanceWizard(models.TransientModel):
    """Wizard for calculating employee attendance from biometric logs."""
    _name = 'attendance.calc.wizard'
    _description = 'attendance calc wizard'

    def calculate_attendance(self):
        """Processes biometric logs to update or create attendance records."""
        minimal_attendance = self.env['ir.config_parameter'].sudo().get_param(
            'dnd_hr_biometric_attendance.minimal_attendance')
        hr_attendance = self.env['hr.attendance']
        today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        domain = [('punching_time', '<=', str(today)), ('is_calculated', '=', False)]
        attendance_log = self.env['attendance.log'].search(domain)
        for log in attendance_log:
            if minimal_attendance:
                attendance = self.env['hr.attendance'].search(
                    [('employee_id', '=', log.employee_id.id),
                     ('punch_date', '=', log.punching_time.date())])
                if attendance:
                    attendance.write({'check_out': log.punching_time})
                else:
                    last_attendance_before_check_out = self.env['hr.attendance'].search([
                        ('employee_id', '=', log.employee_id.id),
                        ('check_out', '=', False)
                    ], order='check_in desc', limit=1)
                    if last_attendance_before_check_out:
                        check_out_time = last_attendance_before_check_out.check_in.replace(hour=23, minute=59,
                                                                                           second=59)
                        last_attendance_before_check_out.write({'check_out': check_out_time})
                    hr_attendance.create({'employee_id': log.employee_id.id,
                                          'check_in': log.punching_time})
            else:
                try:
                    with self.env.cr.savepoint():
                        self._apply_punch(log)
                except Exception as error:
                    _logger.exception("Could not apply punch %s for %s: %s",
                                      log.punching_time, log.employee_id.name, error)
                    continue
            log.is_calculated = True

    def _apply_punch(self, log):
        open_attendance = self._open_attendance_same_day(log)
        if log.status == CHECK_OUT:
            if open_attendance:
                open_attendance.write({'check_out': log.punching_time})
            else:
                _logger.info("Check out for %s at %s has no check in on the same day, skipped",
                             log.employee_id.name, log.punching_time)
            return
        if open_attendance:
            _logger.info("Check in for %s at %s while already checked in, skipped",
                         log.employee_id.name, log.punching_time)
            return
        self._close_earlier_open_attendances(log)
        self.env['hr.attendance'].create({'employee_id': log.employee_id.id,
                                          'check_in': log.punching_time})

    def _close_earlier_open_attendances(self, log):
        day_start, _ = self._local_day_bounds(log.punching_time, log.device_id.time_zone)
        stale = self.env['hr.attendance'].search(
            [('employee_id', '=', log.employee_id.id), ('check_out', '=', False),
             ('check_in', '<', day_start)])
        for attendance in stale:
            _, end_of_its_day = self._local_day_bounds(attendance.check_in, log.device_id.time_zone)
            attendance.write({'check_out': end_of_its_day})
            _logger.info("Closed stale attendance for %s opened %s at end of that day",
                         log.employee_id.name, attendance.check_in)

    def _open_attendance_same_day(self, log):
        if not log.punching_time or not log.employee_id:
            return self.env['hr.attendance']
        day_start, day_end = self._local_day_bounds(log.punching_time, log.device_id.time_zone)
        return self.env['hr.attendance'].search(
            [('employee_id', '=', log.employee_id.id), ('check_out', '=', False),
             ('check_in', '>=', day_start), ('check_in', '<=', day_end)],
            order='check_in desc', limit=1)

    def _local_day_bounds(self, moment, time_zone):
        zone = pytz.timezone(time_zone or self.env.user.tz or 'UTC')
        local_moment = pytz.utc.localize(moment).astimezone(zone)
        local_start = local_moment.replace(hour=0, minute=0, second=0, microsecond=0)
        local_end = local_start + timedelta(days=1) - timedelta(seconds=1)
        return (local_start.astimezone(pytz.utc).replace(tzinfo=None),
                local_end.astimezone(pytz.utc).replace(tzinfo=None))

    def check_in_check_out(self, emp_id, time):
        """Retrieves the ID of the latest check-in record for an employee that has no check-out time."""
        log = self.env['attendance.log'].new({'employee_id': emp_id, 'punching_time': time})
        return self._open_attendance_same_day(log).id
