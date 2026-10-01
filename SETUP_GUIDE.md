# ZKteco Biometric Attendance Integration - Setup Guide

## Overview

The `dnd_hr_biometric_attendance` module provides seamless integration between ZKteco biometric devices and Odoo's HR Attendance system. This module allows for automatic synchronization of employee attendance data from biometric devices to Odoo.

## Prerequisites

### System Requirements

- Odoo 17.0 or later
- Python 3.8+
- Network connectivity between Odoo server and biometric devices
- ZKteco biometric devices (compatible models)

### Required Odoo Modules

- `hr_attendance` (automatically installed as dependency)

## Installation Steps

### 1. Module Installation

1. Copy the `dnd_hr_biometric_attendance` module to your Odoo addons directory:

   ```bash
   cp -r dnd_hr_biometric_attendance /path/to/odoo/addons/
   ```

2. Update the apps list in Odoo:
   - Go to Apps menu
   - Click "Update Apps List"
   - Search for "ZKteco Biometric Attendance Integration"
   - Click "Install"

### 2. Initial Configuration

#### Configure General Settings

1. Navigate to: **Settings > General Settings**
2. Scroll to the **ZKteco Biometric** section
3. Enable **Calculate attendance for each day only** if needed

#### Configure Device Connection

1. Go to **HR > Configuration > Biometric Device Configuration**
2. Click **Create** to add a new device
3. Fill in the required information:
   - **Name**: Descriptive name for your device
   - **Device IP**: IP address of your ZKteco device
   - **Port**: Device port (usually 4370)
   - **Is Password Set**: Check if device has password protection
   - **Device Password**: Enter device password (numeric only)
   - **Timezone**: Select appropriate timezone

### 3. Device Setup

#### Test Device Connection

1. In the Biometric Device Configuration form
2. Click **Test Device Connection**
3. Verify successful connection message

#### Sync Employees to Device

1. Ensure all employees are created in Odoo HR
2. Add **Card Number** to employee records (optional but recommended)
3. Click **Sync Employees** in device configuration
4. This will:
   - Create biometric user IDs for employees
   - Upload employee data to the device
   - Link employees with device records

## Configuration Details

### Employee Setup

For each employee, you can configure:

1. **Biometric User ID**: Automatically generated during sync
2. **Card Number**: Optional field for card-based authentication
3. **Biometric Devices**: Shows which devices the employee is registered on

### Device Parameters

| Parameter | Description            | Default | Required |
| --------- | ---------------------- | ------- | -------- |
| Name      | Device identifier      | -       | Yes      |
| Device IP | IP address of device   | -       | Yes      |
| Port      | Communication port     | 4370    | Yes      |
| Password  | Device access password | -       | No       |
| Timezone  | Device timezone        | GMT     | Yes      |

## Usage Instructions

### Daily Operations

#### Download Attendance Logs

1. **Manual Download**:

   - Go to device configuration
   - Click **Download Attendance Log**
   - System will fetch and process all attendance records

2. **Automatic Download**:
   - Configure cron job (if available in data files)
   - Set desired frequency for automatic synchronization

#### View Attendance Logs

1. Navigate to **HR > Attendance > Attendance Logs**
2. View raw attendance data from devices
3. Check status (Check-in/Check-out)
4. Verify employee assignments

#### Process Attendance Records

1. Go to **HR > Attendance > Calculate Attendance**
2. Select date range
3. Choose employees or leave blank for all
4. Click **Calculate** to process attendance logs into HR attendance records

### Wizards and Tools

#### Attendance Calculation Wizard

- **Purpose**: Convert raw attendance logs to HR attendance records
- **Location**: HR > Attendance > Calculate Attendance
- **Parameters**: Date range, employee selection

#### Attendance Report Wizard

- **Purpose**: Generate attendance reports
- **Location**: HR > Attendance > Attendance Report
- **Output**: Detailed attendance analysis

## Security and Access Rights

### User Groups

| Group                 | Permissions    | Access Level                |
| --------------------- | -------------- | --------------------------- |
| HR Attendance Manager | Full access    | Create, Read, Write, Delete |
| HR Attendance User    | Limited access | Read, Write (own records)   |

### Model Access

- **biometric.config**: Device configuration management
- **attendance.log**: Raw attendance data from devices
- **biometric.attendance.devices**: Employee-device relationships

## Troubleshooting

### Common Issues

#### Connection Problems

**Issue**: "Connection Failed" error
**Solutions**:

1. Verify device IP address and port
2. Check network connectivity: `ping device_ip`
3. Ensure device is powered on and functioning
4. Verify password if device is password-protected
5. Check firewall settings on both server and device

#### Sync Issues

**Issue**: Employees not syncing to device
**Solutions**:

1. Ensure employees have valid names
2. Check device memory capacity
3. Verify device user limit not exceeded
4. Clear device memory if needed

#### Attendance Log Problems

**Issue**: Attendance logs not downloading
**Solutions**:

1. Check device clock synchronization
2. Verify timezone settings match
3. Ensure sufficient disk space on Odoo server
4. Check device attendance log capacity

#### Data Inconsistencies

**Issue**: Duplicate or missing attendance records
**Solutions**:

1. Run attendance calculation wizard
2. Check for duplicate biometric user IDs
3. Verify employee-device mappings
4. Review attendance log status field

### Error Messages

#### "Two Users have same Biometric User ID"

- **Cause**: Multiple employees assigned same device user ID
- **Solution**: Re-sync employees or manually assign unique IDs

#### "Device password should only contain numeric characters"

- **Cause**: Non-numeric characters in password field
- **Solution**: Enter password using numbers only

#### "Connection Failed"

- **Cause**: Network connectivity or device configuration issues
- **Solution**: Follow connection troubleshooting steps above

## Maintenance

### Regular Tasks

1. **Weekly**: Download attendance logs
2. **Monthly**: Review and clean old attendance logs
3. **Quarterly**: Verify employee-device synchronization
4. **Annually**: Update device firmware if needed

### Backup Considerations

- Backup attendance logs before major updates
- Export employee biometric mappings
- Document device configurations

### Performance Optimization

1. Set appropriate cron job frequencies
2. Archive old attendance logs
3. Monitor device memory usage
4. Regular device maintenance

## Advanced Configuration

### Custom Timezone Handling

The module supports timezone conversion for accurate attendance tracking:

- Device timezone setting in configuration
- Automatic UTC conversion for database storage
- Local timezone display in user interface

### Card Number Integration

Enhanced support for card-based authentication:

- Card numbers stored in employee records
- Automatic card sync during employee synchronization
- Card-based attendance tracking

### Multi-Device Support

- Configure multiple biometric devices
- Employee registration across multiple devices
- Centralized attendance log management
- Device-specific attendance tracking

## Support and Documentation

### Additional Resources

- **Live Demo**: Available via YouTube link in module manifest
- **Module Documentation**: Check `doc/index.rst` for technical details
- **Security Model**: Review `security/security.xml` for custom access rules

### Contact Information

- **Developer**: Technaureus Info Solutions Pvt. Ltd.
- **Website**: http://www.technaureus.com/
- **License**: Proprietary License

---

_This guide covers the essential setup and configuration steps for the ZKteco Biometric Attendance Integration module. For advanced customization or specific requirements, consult the module's source code or contact the developer._
