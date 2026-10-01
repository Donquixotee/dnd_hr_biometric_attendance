# -*- coding: utf-8 -*-
# This module and its content is copyright of DND Consulting.
# - © DND Consulting 2025. All rights reserved.

from datetime import datetime
import base64
import io
import math
import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools.misc import xlsxwriter


class AttendanceReportWizard(models.TransientModel):
    """This model represents a wizard for generating attendance reports."""
    _name = 'attendance.report.wizard'
    _description = 'attendance report wizard'

    report_from = fields.Selection([('attend', 'From Attendance'),
                                    ('log', 'From Log')],
                                   string='Report', required=True, default='attend')
    date_from = fields.Datetime('From', required=True, default=datetime.today())
    date_to = fields.Datetime('To', required=True, default=datetime.today())
    report_file = fields.Binary('File', readonly=True)
    report_name = fields.Text(string='File Name')
    is_printed = fields.Boolean('Printed', default=False)

    @api.onchange('report_from')
    def onchange_report(self):
        """Updates the date_from and date_to fields based on the current date
        when the report_from field is changed."""
        day = datetime.today().day
        date_from = datetime.today() + relativedelta(day=day - 1, hour=00, minute=00, second=00)
        date_to = datetime.today() + relativedelta(day=day - 1, hour=23, minute=59, second=59)
        self.date_from = date_from.strftime("%Y-%m-%d %H:%M:%S")
        self.date_to = date_to.strftime("%Y-%m-%d %H:%M:%S")

    def export_attendance_xlsx(self, fl=None):
        """Generates an Excel report based on the selected report type
        (Attendance or Log) and date range"""
        if fl == None:
            fl = ''
        if self.report_from == 'log':
            date_from = self.new_timezone(self.date_from)
            date_to = self.new_timezone(self.date_to)

            domain = [('punching_time', '>=', date_from),
                      ('punching_time', '<=', date_to)]
            attendance_logs = self.env['attendance.log'].search(domain)
            fl = self.print_attendance_logs(attendance_logs)
        elif self.report_from == 'attend':
            date_from = self.new_timezone(self.date_from)
            date_to = self.new_timezone(self.date_to)
            domain = ['|',
                      '&', ('check_in', '>=', date_from), ('check_out', '<=', date_to),
                      '&', '&', ('check_in', '>=', date_from), ('check_in', '<=', date_to), ('check_out', '=', False)]
            attendances = self.env['hr.attendance'].search(domain)
            fl = self.print_attendance_records(attendances)

        output = base64.encodebytes(fl[1])
        ctx = dict(self.env.context)
        ctx.update({'report_file': output, 'file': fl[0]})
        self.report_name = fl[0]
        self.report_file = output
        self.is_printed = True

        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'attendance.report.wizard',
            'target': 'new',
            'context': ctx,
            'res_id': self.id,
        }

    def action_back(self):
        """Resets the is_printed field and returns the action to
        display the attendance report wizard form view."""
        if self._context is None:
            self._context = {}
        self.is_printed = False
        result = {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'attendance.report.wizard',
            'target': 'new',
        }
        return result

    def print_attendance_records(self, attendances):
        """Generates an Excel report for attendance records within the specified date range."""
        str_date1 = str(self.date_from)
        str_date1 = self.new_timezone(self.date_from)

        date1 = datetime.strptime(str_date1, '%Y-%m-%d %H:%M:%S').date()
        day1 = date1.strftime('%d')
        month1 = date1.strftime('%B')
        year1 = date1.strftime('%Y')
        str_date2 = str(self.date_to)
        str_date2 = self.new_timezone(self.date_to)
        date2 = datetime.strptime(str_date2, '%Y-%m-%d %H:%M:%S').date()
        day2 = date2.strftime('%d')
        month2 = date2.strftime('%B')
        year2 = date2.strftime('%Y')
        fl = f'Attendance_Report_{day1}{month1}{year1}_to_{day2}{month2}{year2}.xlsx'

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Attendance Report')
        worksheet.set_landscape()
        worksheet.set_paper(9)  # A4 paper

        # Define professional color schemes
        header_bg = '#1F4788'  # Dark blue
        subheader_bg = '#4472C4'  # Medium blue
        row_alt_bg = '#F2F2F2'  # Light gray

        # Title format
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': header_bg,
            'font_color': 'white',
            'border': 1
        })

        # Header format
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': subheader_bg,
            'font_color': 'white',
            'border': 1,
            'text_wrap': True
        })

        # Data formats
        name_format = workbook.add_format({
            'align': 'left',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter'
        })

        name_format_alt = workbook.add_format({
            'align': 'left',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter',
            'bg_color': row_alt_bg
        })

        data_format = workbook.add_format({
            'align': 'center',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter'
        })

        data_format_alt = workbook.add_format({
            'align': 'center',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter',
            'bg_color': row_alt_bg
        })

        time_format = workbook.add_format({
            'align': 'center',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter',
            'num_format': 'dd/mm/yyyy hh:mm'
        })

        time_format_alt = workbook.add_format({
            'align': 'center',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter',
            'bg_color': row_alt_bg,
            'num_format': 'dd/mm/yyyy hh:mm'
        })

        # Set column widths
        worksheet.set_column('A:A', 5)   # No.
        worksheet.set_column('B:B', 30)  # Employee Name
        worksheet.set_column('C:C', 20)  # Check In
        worksheet.set_column('D:D', 20)  # Check Out
        worksheet.set_column('E:E', 15)  # Duration
        worksheet.set_column('F:XFD', None, None, {'hidden': True})

        # Title row
        worksheet.set_row(0, 30)
        worksheet.merge_range('A1:E1',
                              f"Attendance Report: {day1} {month1} {year1} - {day2} {month2} {year2}",
                              title_format)

        # Header row
        row = 2
        worksheet.set_row(row, 25)
        worksheet.write(row, 0, "No.", header_format)
        worksheet.write(row, 1, "Employee Name", header_format)
        worksheet.write(row, 2, "Check In", header_format)
        worksheet.write(row, 3, "Check Out", header_format)
        worksheet.write(row, 4, "Duration (HH:MM)", header_format)

        # Data rows
        row += 1
        for index, attendance in enumerate(attendances, start=1):
            # Alternate row colors
            is_alt = index % 2 == 0
            n_fmt = name_format_alt if is_alt else name_format
            d_fmt = data_format_alt if is_alt else data_format

            worksheet.write(row, 0, index, d_fmt)
            worksheet.write(row, 1, attendance.employee_id.name or 'N/A', n_fmt)

            if attendance.check_in:
                check_in = self.new_timezone(attendance.check_in)
                worksheet.write(row, 2, check_in, d_fmt)
            else:
                worksheet.write(row, 2, 'No Check In', d_fmt)

            if attendance.check_out:
                check_out = self.new_timezone(attendance.check_out)
                worksheet.write(row, 3, check_out, d_fmt)
            else:
                worksheet.write(row, 3, 'No Check Out', d_fmt)

            # Calculate duration
            factor = attendance.in_out_diff < 0 and -1 or 1
            val = abs(attendance.in_out_diff)
            hour, minute = (factor * int(math.floor(val)), int(round((val % 1) * 60)))
            if minute == 60:
                hour += 1
                minute = 0
            diff = f"{hour:02d}:{minute:02d}"
            worksheet.write(row, 4, diff, d_fmt)
            row += 1

        # Add summary
        if attendances:
            row += 1
            summary_format = workbook.add_format({
                'bold': True,
                'font_size': 11,
                'align': 'right',
                'bg_color': '#E7E6E6',
                'border': 1
            })
            worksheet.merge_range(row, 0, row, 3, f"Total Records: {len(attendances)}", summary_format)

        workbook.close()
        xlsx_data = output.getvalue()

        return [fl, xlsx_data]

    def new_timezone(self, time):
        """Converts a datetime string from UTC to the local timezone."""
        user_tz = self.env.user.tz or str(pytz.utc)
        local = pytz.timezone(user_tz)
        display_date_result = datetime.strftime(pytz.utc.localize(time, is_dst=0).astimezone(
            local), "%Y-%m-%d %H:%M:%S")
        return display_date_result

    def to_naive_user_tz(self, datetime):
        """ Converts a UTC datetime to the user's local timezone."""
        tz_name = self.env.user.tz
        tz = tz_name and pytz.timezone(tz_name) or pytz.UTC
        x = pytz.UTC.localize(datetime.replace(tzinfo=None), is_dst=False).astimezone(tz).replace(tzinfo=None)
        return x

    def to_naive_utc(self, datetime):
        """Converts a datetime from the user's local timezone to UTC."""
        tz_name = self.env.user.tz
        tz = tz_name and pytz.timezone(tz_name) or pytz.UTC
        y = tz.localize(datetime.replace(tzinfo=None), is_dst=False).astimezone(pytz.UTC).replace(tzinfo=None)
        return y

    def to_tz(self, datetime):
        """Converts a UTC datetime to the user's local timezone."""
        tz_name = self.env.user.tz
        tz = pytz.timezone(tz_name) if tz_name else pytz.UTC
        return pytz.UTC.localize(datetime.replace(tzinfo=None), is_dst=False).astimezone(tz).replace(tzinfo=None)

    def convert_timezone(self, time):
        """Converts a datetime string from the user's local timezone to UTC and back to a string."""
        atten_time = datetime.strptime(str(time), '%Y-%m-%d %H:%M:%S')
        atten_time = datetime.strptime(
            atten_time.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
        local_tz = pytz.timezone(
            self.env.user.tz or 'GMT')
        local_dt = local_tz.localize(atten_time, is_dst=0)
        utc_dt = local_dt.astimezone(pytz.utc)
        utc_dt = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
        atten_time = datetime.strptime(
            utc_dt, "%Y-%m-%d %H:%M:%S")
        atten_time = fields.Datetime.to_string(atten_time)
        return atten_time

    def print_attendance_logs(self, logs):
        """Generates an Excel report of attendance logs."""
        str_date1 = str(self.date_from)
        date1 = datetime.strptime(str(str_date1), '%Y-%m-%d %H:%M:%S').date()
        day1 = date1.strftime('%d')
        month1 = date1.strftime('%B')
        year1 = date1.strftime('%Y')
        str_date2 = str(self.date_to)
        date2 = datetime.strptime(str(str_date2), '%Y-%m-%d %H:%M:%S').date()
        day2 = date2.strftime('%d')
        month2 = date2.strftime('%B')
        year2 = date2.strftime('%Y')
        fl = f'Attendance_Log_{day1}{month1}{year1}_to_{day2}{month2}{year2}.xlsx'

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Attendance Log')
        worksheet.set_landscape()
        worksheet.set_paper(9)  # A4 paper

        # Define professional color schemes
        header_bg = '#1F4788'  # Dark blue
        subheader_bg = '#4472C4'  # Medium blue
        row_alt_bg = '#F2F2F2'  # Light gray
        check_in_bg = '#D4EDDA'  # Light green
        check_out_bg = '#F8D7DA'  # Light red

        # Title format
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': header_bg,
            'font_color': 'white',
            'border': 1
        })

        # Header format
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': subheader_bg,
            'font_color': 'white',
            'border': 1,
            'text_wrap': True
        })

        # Data formats
        name_format = workbook.add_format({
            'align': 'left',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter'
        })

        name_format_alt = workbook.add_format({
            'align': 'left',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter',
            'bg_color': row_alt_bg
        })

        data_format = workbook.add_format({
            'align': 'center',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter'
        })

        data_format_alt = workbook.add_format({
            'align': 'center',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter',
            'bg_color': row_alt_bg
        })

        # Status formats (Check In/Out)
        check_in_format = workbook.add_format({
            'align': 'center',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter',
            'bg_color': check_in_bg,
            'bold': True
        })

        check_out_format = workbook.add_format({
            'align': 'center',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter',
            'bg_color': check_out_bg,
            'bold': True
        })

        # Set column widths
        worksheet.set_column('A:A', 5)   # No.
        worksheet.set_column('B:B', 30)  # Employee Name
        worksheet.set_column('C:C', 20)  # Punching Time
        worksheet.set_column('D:D', 15)  # Status
        worksheet.set_column('E:E', 20)  # Device
        worksheet.set_column('F:XFD', None, None, {'hidden': True})

        # Title row
        worksheet.set_row(0, 30)
        worksheet.merge_range('A1:E1',
                              f"Attendance Log Report: {day1} {month1} {year1} - {day2} {month2} {year2}",
                              title_format)

        # Header row
        row = 2
        worksheet.set_row(row, 25)
        worksheet.write(row, 0, "No.", header_format)
        worksheet.write(row, 1, "Employee Name", header_format)
        worksheet.write(row, 2, "Punching Time", header_format)
        worksheet.write(row, 3, "Status", header_format)
        worksheet.write(row, 4, "Device", header_format)

        # Data rows
        row += 1
        for index, log in enumerate(logs, start=1):
            # Alternate row colors for name column
            is_alt = index % 2 == 0
            n_fmt = name_format_alt if is_alt else name_format
            d_fmt = data_format_alt if is_alt else data_format

            worksheet.write(row, 0, index, d_fmt)
            worksheet.write(row, 1, log.employee_id.name or 'N/A', n_fmt)

            if log.punching_time:
                punching_time = self.new_timezone(log.punching_time)
                worksheet.write(row, 2, punching_time, d_fmt)
            else:
                worksheet.write(row, 2, 'No Time', d_fmt)

            # Status with color coding
            if log.status == "0":
                status = 'Check In'
                status_fmt = check_in_format
            elif log.status == "1":
                status = 'Check Out'
                status_fmt = check_out_format
            else:
                status = 'Unknown'
                status_fmt = d_fmt

            worksheet.write(row, 3, status, status_fmt)
            worksheet.write(row, 4, log.device or 'N/A', d_fmt)
            row += 1

        # Add summary
        if logs:
            row += 1
            summary_format = workbook.add_format({
                'bold': True,
                'font_size': 11,
                'align': 'right',
                'bg_color': '#E7E6E6',
                'border': 1
            })
            check_ins = len([l for l in logs if l.status == "0"])
            check_outs = len([l for l in logs if l.status == "1"])
            worksheet.merge_range(row, 0, row, 4,
                                f"Total: {len(logs)} records | Check Ins: {check_ins} | Check Outs: {check_outs}",
                                summary_format)

        workbook.close()
        xlsx_data = output.getvalue()

        return [fl, xlsx_data]
