# ZKTeco Biometric Attendance Integration (Odoo 17)

Records employee attendance in Odoo 17 from ZKTeco biometric readers.

Punches are collected from the readers, stored as attendance logs, and paired into standard
`hr.attendance` records, so the regular Attendances app, reporting and payroll work unchanged.

## Requirements

- Odoo 17.0
- `hr_attendance`
- Network access to the readers on TCP/UDP port 4370

The pyzk protocol library is vendored in `zk/`, so there is nothing to install with pip.

## Two ways to reach the readers

A reader only answers hosts that can route to it, and most are on a private network with no
gateway. Each device record declares how Odoo reaches it.

### Direct

Odoo connects to the reader itself. Use this when Odoo runs on the same network as the readers.
A scheduled job polls each device every five minutes.

### Remote Agent

Odoo cannot reach the reader, typically because Odoo is hosted outside the client's network. An
agent runs on a machine inside that network, reads the punches locally and pushes them to Odoo
over outbound HTTPS. Nothing connects inward, so no VPN or port forwarding is needed.

The agent lives in a separate repository, `service_zkteco_daemon`. In this mode Odoo never
contacts the device, and operations that write to a reader are refused with an explanation
rather than timing out.

## Installation

1. Copy the module into the Odoo addons path.
2. Update the apps list and install **ZKteco Biometric Attendance Integration**.
3. Open **Biometric Attendance** in the main menu.

## Configuring a device

**Biometric Attendance > Configuration > Biometric Devices**

| Field | Purpose |
|---|---|
| Name | Free text, shown throughout the interface |
| Device IP, Port | Reader address, usually port 4370. Ignored in Remote Agent mode |
| Serial Number | Identifies the reader to the agent. Required in Remote Agent mode |
| Timezone | The reader's own clock timezone. Punch times are converted from it to UTC |
| Connection Mode | Direct or Remote Agent |
| Punch Direction | How to interpret punches from this reader, see below |
| Connection Timeout | Seconds to wait for the reader |
| Force UDP | Skip the TCP attempt. Needed by some older firmware such as the K40 and K50 |
| Skip Ping Check | Connect without pinging first, for networks that block ICMP |
| Agent Last Seen | Updated whenever a remote agent contacts Odoo. Use it to confirm the agent is alive |

Getting the timezone wrong shifts every punch, and nothing downstream can correct it.

### Punch direction

- **Alternate** — one reader is used for both entering and leaving, so punches alternate
  check in, check out, check in.
- **Always Check In** / **Always Check Out** — the reader guards one direction only, as with a
  separate entrance and exit.

With separate entrance and exit readers, leaving both on Alternate records somebody who enters
on three consecutive days as in, out, in.

## Linking employees

A punch carries the identifier the reader knows the person by. Odoo records which employee that
identifier belongs to, per reader, under the employee's **Biometric Devices** tab.

The employee's **Badge ID** is used as that identifier. It must be digits only and no more than
nine of them. Odoo's own Generate button produces twelve digits, which the readers cannot store,
so type the number printed on the badge instead.

**Biometric Status** on the employee says where they stand:

| Status | Meaning |
|---|---|
| Needs a badge number | Nothing will happen until a Badge ID is filled in |
| Badge number not usable | Too long, or not digits |
| Waiting to be sent | Will be written to the readers on the next agent cycle |
| On some readers | Reached some readers but not all |
| On all readers | Present everywhere, ready to enrol a fingerprint |

Punches from an identifier that no employee claims are counted and logged, never recorded.
Enrolling somebody on a reader does not create them in Odoo.

## How attendance is produced

1. Punches arrive and become **Attendance Logs**.
2. A scheduled job pairs them into `hr.attendance`.

Pairing rules:

- A check out closes a check in **from the same calendar day**, in the reader's timezone,
  unless a pairing window is configured.
- A check out with no matching check in that day is logged and skipped, never attached to an
  older record.
- A check in while already checked in is skipped.
- A check in first closes any attendance still open from an earlier day, at the end of that day.
- Each punch is applied independently, so one problem punch cannot stop the rest.

Somebody who forgets to badge out is left with an open attendance, which is visible in the
Attendances app for HR to correct.

### Shifts that cross midnight

By default a check out only closes a check in from the same calendar day. A shift running from
22:00 to 06:00, or an evening shift that overruns past midnight, would never pair and the person
is left with an open attendance.

Set **Pairing Window (hours)** under Settings, Attendances, to the longest shift plus any
expected overrun. A check out then closes the most recent check in within that many hours,
whatever the date. Leave it at 0 for sites that work only within a calendar day.

Shifts such as 07:30 to 15:30 and 15:30 to 23:30 stay inside one day and need no window, but a
window still protects against somebody badging out after midnight.

### Scheduled jobs

| Job | Interval | Purpose |
|---|---|---|
| Biometric: Download Attendance Logs | 5 minutes | Reads devices in Direct mode. Skips Remote Agent devices |
| Biometric: Calculate Attendance | 5 minutes | Pairs logs into attendance |

## Reports

**Biometric Attendance > Reports** exports attendance to xlsx, either from the paired
attendance records or from the raw punch logs, over a chosen period.

## Interface for the remote agent

The agent calls these methods on `biometric.config` over XML-RPC. They are the only entry
points it uses.

| Method | Purpose |
|---|---|
| `action_receive_punches(serial_number, punches)` | Deliver punches. Returns how many were stored, how many were already known, and any unrecognised identifiers |
| `action_pending_device_users(serial_number)` | Ask which employees are missing from that reader |
| `action_confirm_device_users(serial_number, results)` | Report what was written, so Odoo records the links |

Delivery is idempotent. `attendance.log` carries a unique constraint on device, device user and
punch time, so re-sending a punch stores nothing. All three methods stamp Agent Last Seen.

The Odoo account the agent authenticates as needs **Attendances / Administrator** and must be
allocated to the company that owns the devices, otherwise records are silently rejected by the
access rules.

## Operations that write to a reader

Uploading users, deleting users and triggering enrolment all require Odoo to reach the device,
so they work in Direct mode only. In Remote Agent mode they refuse with an explanation.

Two of them are destructive and cannot be undone:

- Deleting a user removes their fingerprint templates. Odoo never holds biometric data, so they
  can only be recreated by that person enrolling again in person.
- Writing a user to an identifier already in use overwrites whoever held it.

Fingerprint templates are stored against the reader's internal user index, not the badge number.
Rewriting every user on a populated reader reassigns those indexes and detaches enrolled
fingerprints from their owners. Add people individually instead.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Cannot reach device, ping failed | ICMP blocked. Enable Skip Ping Check |
| Connection times out | Port 4370 blocked, or a COMM key is set on the reader. Clear it on the device, or put the same number in Device Password. K40 and K50 firmware often needs Force UDP |
| Punches recorded hours out | Device record timezone does not match the reader's clock |
| Attendance logs appear but no attendance | The Calculate Attendance job is inactive |
| Punches for users not linked to any employee | Those identifiers have no employee. Fill in Badge IDs |
| Nothing arrives, Agent Last Seen is old | The agent is not running or cannot reach Odoo |
| Everyone shows large negative extra hours | Standard Odoo comparing worked time against each employee's Working Schedule, not a fault of this module |

## Development

```bash
odoo -d <database> -i dnd_hr_biometric_attendance \
     --test-enable --test-tags /dnd_hr_biometric_attendance --stop-after-init
```

Tests cover punch processing, the pairing rules, the agent entry points, badge validation and
the report export. They need no hardware.

## Licence

LGPL-3. Author: DND Consulting, Amraoui Sofiane.
