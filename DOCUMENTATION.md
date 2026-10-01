# ZKteco Biometric Attendance Integration - Code Documentation

## Table of Contents

1. [Overview](#overview)
2. [Module Structure](#module-structure)
3. [Core Components](#core-components)
4. [API Reference](#api-reference)
5. [Data Flow](#data-flow)
6. [Usage Guide](#usage-guide)
7. [Troubleshooting](#troubleshooting)

---

## Overview

This module provides seamless integration between Odoo 18.0 and ZKteco biometric devices for employee attendance tracking. It supports bidirectional synchronization, allowing you to:

- Upload employees from Odoo to biometric devices
- Import users from biometric devices to Odoo
- Download attendance logs from devices
- Manage employee card numbers and biometric IDs

**Version:** 18.0.1.0
**Developer:** Amraoui Sofiane
**Company:** DND Consulting
**License:** LGPL-3

---

## Module Structure

```
dnd_hr_biometric_attendance/
├── __init__.py                 # Module initialization
├── __manifest__.py             # Module metadata and dependencies
├── models/                     # Data models
│   ├── __init__.py
│   ├── biometric_device_config.py    # Device configuration & sync logic
│   ├── attendance_log.py             # Attendance log records
│   ├── hr_employee.py                # Employee biometric data
│   └── res_config_settings.py        # Configuration settings
├── wizard/                     # Wizard dialogs
│   ├── __init__.py
│   ├── attendance_calc_wizard.py     # Attendance calculation
│   ├── attendance_report_wizard.py   # Attendance reports
│   └── biometric_device_wizard.py    # Device operations
├── views/                      # UI definitions
│   ├── biometric_device_config_view.xml
│   ├── attendance_log_view.xml
│   ├── hr_employee_view.xml
│   ├── hr_attendance_view.xml
│   ├── res_config_settings.xml
│   └── menu.xml
├── security/                   # Access control
│   ├── ir.model.access.csv
│   └── security.xml
├── data/                       # Default data
│   └── biometric_data.xml
└── zk/                         # ZKteco device library
    ├── __init__.py
    ├── base.py                 # Core ZK protocol implementation
    ├── user.py                 # User data structures
    ├── attendance.py           # Attendance data structures
    ├── finger.py               # Fingerprint data structures
    ├── const.py                # Protocol constants
    └── exception.py            # Custom exceptions
```

---

## Core Components

### 1. Biometric Device Configuration (`biometric_device_config.py`)

The main model that handles all device operations and synchronization logic.

#### Key Fields:

- `name` - Device identifier
- `device_ip` - IP address of the device
- `port` - Communication port (default: 4370)
- `is_password_set` - Whether device requires password
- `device_password` - Numeric password for device
- `time_zone` - Device timezone for attendance log conversion
- `company_id` - Multi-company support

#### Main Methods:

**Device Connection:**

```python
def _connect_to_device(self)
```

Establishes connection to the biometric device.

- **Returns:** ZK connection object
- **Raises:** ValidationError if connection fails

**Sync Employees to Device:**

```python
def sync_employees(self)
```

Uploads ALL Odoo employees to the biometric device.

- Checks device capacity before upload
- Links to existing device users by name
- Creates new users with incremented IDs
- Updates card numbers for existing users
- **Returns:** Success wizard dialog

**Sync Employees from Device:**

```python
def sync_employees_from_device(self)
```

Imports ALL users from device to Odoo.

- Creates new employees if not found
- Links to existing employees by name
- Updates card numbers from device
- **Returns:** Success notification with counts

**Download Attendance Logs:**

```python
def download_attendance_log(self)
```

Downloads attendance records from device.

- Converts device timezone to UTC
- Determines check-in/check-out status
- Creates or updates attendance log records
- **Returns:** Success wizard dialog

---

### 2. Helper Functions (Private Methods)

#### Data Validation & Sanitization:

**`_validate_card_number(employee)`**

```python
def _validate_card_number(self, employee)
```

Validates and converts employee card number to integer.

- **Parameters:** employee - hr.employee record
- **Returns:** int (0 if empty/None)
- **Raises:** UserError if invalid format

**`_sanitize_employee_name(name)`**

```python
def _sanitize_employee_name(self, name)
```

Prepares employee name for device compatibility.

- **Parameters:** name - string
- **Returns:** string (max 24 chars, stripped, default "Unknown")

#### Device User Management:

**`_get_next_available_ids(users)`**

```python
def _get_next_available_ids(self, users)
```

Calculates next available UID and user_id from existing device users.

- **Parameters:** users - list of User objects from device
- **Returns:** tuple (next_uid, next_user_id_str, user_id_list_str)
- **Logic:**
  - Finds biggest UID and increments
  - Finds biggest numeric user_id and increments
  - Handles non-numeric user_ids gracefully

**`_check_device_capacity(zk, employees)`**

```python
def _check_device_capacity(self, zk, employees)
```

Verifies device has sufficient capacity for new employees.

- **Parameters:**
  - zk - ZK connection object
  - employees - recordset of hr.employee
- **Raises:** UserError with capacity details if exceeded

**`_find_user_by_name(emp_name, users)`**

```python
def _find_user_by_name(self, emp_name, users)
```

Searches for existing device user by sanitized name.

- **Parameters:**
  - emp_name - sanitized employee name (24 chars)
  - users - list of User objects from device
- **Returns:** User object or None

#### Employee-Device Linking:

**`_link_employee_to_existing_user(employee, existing_user, zk)`**

```python
def _link_employee_to_existing_user(self, employee, existing_user, zk)
```

Links Odoo employee to existing device user.

- **Parameters:**
  - employee - hr.employee record
  - existing_user - User object from device
  - zk - ZK connection object
- **Actions:**
  - Creates biometric_device_ids link
  - Updates card number on device if provided

**`_create_new_user_on_device(employee, uid, next_user_id, zk)`**

```python
def _create_new_user_on_device(self, employee, uid, next_user_id, zk)
```

Creates new user on device for Odoo employee.

- **Parameters:**
  - employee - hr.employee record
  - uid - next available UID
  - next_user_id - next available user_id (string)
  - zk - ZK connection object
- **Returns:** string (incremented next_user_id)
- **Actions:**
  - Creates biometric_device_ids link in Odoo
  - Calls zk.set_user() to create on device

**`_update_existing_employee_card(employee, users, zk)`**

```python
def _update_existing_employee_card(self, employee, users, zk)
```

Updates card number for employee already linked to device.

- **Parameters:**
  - employee - hr.employee record
  - users - list of User objects from device
  - zk - ZK connection object
- **Actions:**
  - Finds linked device user
  - Updates card number via zk.set_user()

**`_import_user_from_device(user)`**

```python
def _import_user_from_device(self, user)
```

Imports single user from device to Odoo.

- **Parameters:** user - User object from device
- **Returns:** tuple (created_count, updated_count)
- **Logic:**
  - Skips if already linked (0, 0)
  - Links to existing employee by name (0, 1)
  - Creates new employee if not found (1, 0)

---

### 3. Employee Model Extension (`hr_employee.py`)

#### New Fields:

```python
biometric_device_ids = fields.One2many('biometric.attendance.devices', 'employee_id')
card_number = fields.Char(string="Card Number")
```

#### Biometric Attendance Devices Model:

```python
class BiometricAttendanceDevices(models.Model):
    _name = 'biometric.attendance.devices'

    employee_id = fields.Many2one('hr.employee')
    biometric_attendance_id = fields.Char(string='Biometric User ID', required=True)
    device_id = fields.Many2one('biometric.config', required=True)
```

**Purpose:** Links employees to their device-specific user IDs. One employee can have different IDs on different devices.

---

### 4. Attendance Log (`attendance_log.py`)

Stores raw attendance punches from biometric devices.

#### Key Fields:

- `employee_id` - Related employee
- `punching_time` - Timestamp of punch
- `status` - '0' for check-in, '1' for check-out
- `device` - Device name that recorded the punch
- `is_calculated` - Whether converted to hr.attendance
- `company_id` - Company association

---

### 5. ZK Device Library (`zk/`)

Low-level communication with ZKteco devices using UDP/TCP protocols.

#### Main Classes:

**`ZK(ip, port, password, timeout, force_udp, ommit_ping, verbose, encoding)`**
Core device communication class.

**Key Methods:**

- `connect()` - Establish connection
- `disconnect()` - Close connection
- `get_users()` - Retrieve all users
- `set_user(uid, name, privilege, password, group_id, user_id, card)` - Create/update user
- `delete_user(uid, user_id)` - Remove user
- `get_attendance()` - Download attendance logs
- `clear_attendance()` - Clear device attendance memory
- `disable_device()` - Lock device (prevents local use)
- `enable_device()` - Unlock device
- `read_sizes()` - Get device capacity info

**User Data Structure:**

```python
class User:
    uid          # Internal device UID (integer)
    name         # User display name (string)
    privilege    # Access level (0=user, 14=admin)
    password     # Numeric password (string)
    group_id     # Group identifier (string)
    user_id      # External user ID (string)
    card         # Card number (integer)
```

**Attendance Data Structure:**

```python
class Attendance:
    user_id      # User identifier (string)
    timestamp    # Punch datetime
    status       # Attendance status code
    punch        # Punch type code
    uid          # Internal device UID
```

---

## Data Flow

### Upload Employees to Device Flow:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User clicks "Upload to Device" button                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. sync_employees() method called                          │
│    - Get all hr.employee records                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Connect to device (_connect_to_device)                  │
│    - Establish TCP/UDP connection                          │
│    - Disable device to prevent interference                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Check device capacity (_check_device_capacity)          │
│    - Read device users_cap and current users               │
│    - Calculate employees to add                            │
│    - Raise error if capacity exceeded                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Get existing device users (zk.get_users)                │
│    - Retrieve all users from device                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Calculate next IDs (_get_next_available_ids)            │
│    - Find biggest UID: increment for new users             │
│    - Find biggest user_id: increment for new IDs           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Process each employee (loop)                            │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│ Already linked?  │    │ Not linked to device │
│ - Skip or update │    └──────────┬───────────┘
└──────────────────┘               │
                                   ▼
                        ┌──────────────────────┐
                        │ User exists on       │
                        │ device with same     │
                        │ name?                │
                        └──────┬───────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
        ┌──────────────────────┐  ┌──────────────────────┐
        │ YES: Link to         │  │ NO: Create new user  │
        │ existing user        │  │ on device            │
        │ (_link_employee...)  │  │ (_create_new_user...)│
        └──────────────────────┘  └──────────────────────┘
                    │                     │
                    └──────────┬──────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │ Update card number if needed │
                └──────────────┬───────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. Update existing employees' cards                        │
│    (_update_existing_employee_card for each)               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. Re-enable device and disconnect                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 10. Show success wizard to user                            │
└─────────────────────────────────────────────────────────────┘
```

### Import Users from Device Flow:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User clicks "Import from Device" button                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. sync_employees_from_device() called                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Connect to device (_connect_to_device)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Get all users from device (zk.get_users)                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Process each device user (_import_user_from_device)     │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│ Already linked   │    │ Not linked yet       │
│ to Odoo?         │    │                      │
│ - Skip (0,0)     │    └──────────┬───────────┘
└──────────────────┘               │
                                   ▼
                        ┌──────────────────────┐
                        │ Employee exists in   │
                        │ Odoo with same name? │
                        └──────┬───────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
        ┌──────────────────────┐  ┌──────────────────────┐
        │ YES: Link existing   │  │ NO: Create new       │
        │ employee (0,1)       │  │ employee (1,0)       │
        │ - Update card number │  │ - Set name & card    │
        └──────────────────────┘  └──────────────────────┘
                    │                     │
                    └──────────┬──────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Disconnect from device                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Show notification: X created, Y updated                 │
└─────────────────────────────────────────────────────────────┘
```

### Download Attendance Log Flow:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User clicks "Download Attendance" button                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. download_attendance_log() called                        │
│    - Connect to device                                     │
│    - Call zk.get_attendance()                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Process each attendance record                          │
│    - Convert device timezone to UTC                        │
│    - Find employee by biometric_attendance_id              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Determine check-in/check-out status                     │
│    - Group by user_id                                      │
│    - Sort by timestamp                                     │
│    - Alternate: check-in → check-out → check-in...        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Create/Update attendance.log records                    │
│    - Check if record exists (employee + time)              │
│    - Create new or update existing                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Show success wizard                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Usage Guide

### Initial Setup

1. **Install the module:**

   - Go to Apps → Search "ZKteco Biometric"
   - Click Install

2. **Configure a device:**

   - Navigate to: Attendances → Configuration → Biometric Devices
   - Click Create
   - Fill in:
     - **Name:** e.g., "Main Entrance Device"
     - **Device IP:** e.g., "192.168.1.100"
     - **Port:** 4370 (default)
     - **Timezone:** Select your device location timezone
     - **Password:** (if device has password protection)

3. **Test connection:**
   - Click "Test Connection" button
   - Verify success message

### Uploading Employees to Device

**Scenario:** You have employees in Odoo and want to upload them to the biometric device.

1. Open the biometric device record
2. Click "Upload to Device" button
3. System will:
   - Check if employee name already exists on device
   - If yes: Link to existing device user
   - If no: Create new user with next available ID
   - Update card numbers if provided

**Result:** All Odoo employees are now registered on the device.

### Importing Users from Device

**Scenario:** You have users registered on the device and want to import them to Odoo.

1. Open the biometric device record
2. Click "Import from Device" button
3. System will:
   - Read all users from device
   - Check if employee with same name exists in Odoo
   - If yes: Link existing employee
   - If no: Create new employee
   - Import card numbers

**Result:** All device users are now in Odoo as employees.

### Downloading Attendance Logs

1. Open the biometric device record
2. Click "Download Attendance" button
3. System downloads all punches and creates attendance.log records
4. Navigate to: Attendances → Attendance Logs
5. View/filter downloaded records

### Managing Employee Card Numbers

1. Go to: Employees → Employees
2. Open an employee record
3. Go to "HR Settings" tab
4. Enter/update "Card Number" field
5. Next sync will update the device with new card number

---

## Troubleshooting

### Common Errors

#### "Can't set user"

**Cause:** Device rejected user creation.

**Solutions:**

1. Check device capacity (might be full)
2. Verify employee name is valid (max 24 chars)
3. Check card number format (must be integer)
4. Ensure user_id is not already taken

#### "Connection Failed"

**Cause:** Cannot connect to device.

**Solutions:**

1. Verify device IP address
2. Check network connectivity: `ping [device_ip]`
3. Ensure device port is correct (default: 4370)
4. Check firewall settings
5. Verify device is powered on

#### "Device capacity exceeded"

**Cause:** Device memory full.

**Solutions:**

1. Delete unused users from device
2. Clear old attendance logs: `zk.clear_attendance()`
3. Upgrade device firmware (if supported)

#### "Invalid card number"

**Cause:** Card number contains non-numeric characters.

**Solutions:**

1. Ensure card_number field contains only digits
2. Remove any spaces or special characters
3. Leave blank if no card number

#### Timezone Issues

**Symptom:** Attendance times are incorrect.

**Solutions:**

1. Verify device timezone setting matches device location
2. Check Odoo user timezone
3. Ensure attendance.log records show correct punching_time

### Debug Mode

Enable verbose logging in ZK library:

```python
zk = ZK(ip, port, password=password, verbose=True)
```

This will print detailed protocol communication to logs.

### Testing Connectivity

Use Python shell to test device connection:

```python
from odoo.addons.dnd_hr_biometric_attendance.zk import ZK

zk = ZK('192.168.1.100', 4370, password=0, verbose=True)
conn = zk.connect()
if conn:
    print("Connected successfully!")
    zk.read_sizes()
    print(f"Users: {zk.users}/{zk.users_cap}")
    print(f"Records: {zk.records}/{zk.rec_cap}")
    zk.disconnect()
else:
    print("Connection failed!")
```

---

## Best Practices

### Before Syncing

1. **Backup device data** - Use device management software
2. **Test on non-production device first**
3. **Verify timezone settings**
4. **Check device capacity**

### During Sync

1. **Avoid device usage** - Device is disabled during sync
2. **Don't interrupt process** - Wait for completion
3. **Monitor error messages**

### After Sync

1. **Verify employee count** matches expectations
2. **Test attendance punching** on device
3. **Check attendance logs** download correctly
4. **Review card numbers** are correctly set

### Regular Maintenance

1. **Download attendance logs daily** - Prevents device memory overflow
2. **Sync employees** when new hires join
3. **Update card numbers** when cards are reissued
4. **Clear old attendance logs** from device monthly

---

## Advanced Configuration

### Multi-Device Setup

For multiple biometric devices:

1. Create separate device records for each physical device
2. Each employee can have different biometric_attendance_id per device
3. Download attendance from all devices to consolidate logs

### Custom Attendance Calculation

Extend `attendance_calc_wizard.py` to implement:

- Custom shift rules
- Overtime calculations
- Late arrival penalties
- Break time deductions

### Fingerprint Management

Use `biometric_device_wizard.py` operations:

- **Scan:** Enroll fingerprints on device
- **Update:** Modify user details
- **Remove:** Delete user from device

---

## Security Considerations

### Access Control

The module uses Odoo's security groups:

- `hr_attendance.group_hr_attendance_manager` - Full access
- `hr_attendance.group_hr_attendance` - Read-only access

### Device Password

- Store device passwords securely
- Use numeric passwords only (device limitation)
- Don't share device passwords

### Network Security

- Use private network for device communication
- Implement firewall rules to restrict device access
- Consider VPN for remote device access

---

## Performance Optimization

### Large Employee Counts (1000+)

1. **Batch uploads:** Split employees into groups
2. **Schedule syncs:** During low-usage hours
3. **Increase timeout:** For slow connections
4. **Monitor memory:** Device RAM limitations

### Frequent Attendance Downloads

1. **Schedule cron job:** Download every 4-6 hours
2. **Clear device logs:** After successful download
3. **Use UTC timestamps:** Avoids timezone conversion overhead

---

## API Integration Examples

### Programmatic Employee Upload

```python
# Get device
device = env['biometric.config'].browse(1)

# Upload specific employees
employees = env['hr.employee'].search([('department_id', '=', 5)])
device.with_context(employee_ids=employees.ids).sync_employees()
```

### Custom Attendance Processing

```python
# Get unprocessed attendance logs
logs = env['attendance.log'].search([('is_calculated', '=', False)])

# Process each log
for log in logs:
    # Custom logic here
    # Create hr.attendance record
    log.write({'is_calculated': True})
```

---

## Support & Resources

- **Company Website:** https://dnd-consulting.com/
- **Developer:** Amraoui Sofiane <s.amraoui@dndconsulting.dz>
- **Support:** Contact DND Consulting for professional support

---

**Document Version:** 1.1
**Last Updated:** 2025-12-08
**Module Version:** 18.0.1.0
**Developer:** Amraoui Sofiane
**Company:** DND Consulting
