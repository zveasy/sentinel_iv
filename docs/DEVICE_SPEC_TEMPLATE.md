# Device Spec Template (Microgrid + DC EV Chargers)

Fill in the fields below for your hardware device.

## 1) Device Identity
- Device name:
- Manufacturer:
- Model:
- Hardware revision:
- Firmware version:
- Unique device ID format:
- Serial number format:

## 2) Physical + Electrical
- Power input (V, A, AC/DC):
- Power budget (W):
- Isolation requirements (galvanic, opto):
- Surge protection:
- Operating temperature range:
- Humidity range:
- IP rating:
- Mounting constraints:

## 3) Interfaces
- Ethernet:
- Wi‑Fi / Cellular:
- RS‑485:
- CAN:
- Modbus RTU/TCP:
- Digital I/O:
- USB/Serial:
- Other:

## 4) Time + Sync
- Time source (NTP/GPS/RTC):
- Clock drift tolerance:
- Time sync interval:

## 5) EV Charger Integration
- Charger model(s):
- Protocol(s): OCPP / Modbus / vendor API / other
- Control actions supported:
- Telemetry metrics available:
- Command latency targets:
- Safety interlocks/limits:

## 6) Microgrid Controller Integration
- Controller model(s):
- Protocol(s): Modbus / DNP3 / IEC‑61850 / vendor API / other
- Control actions supported:
- Telemetry metrics available:
- Command latency targets:
- Safety interlocks/limits:

## 7) Data + Telemetry
- Required metrics list:
- Sampling rate:
- Schema version:
- Units and normalization rules:
- Local buffering duration:

## 8) Security
- Device identity (certs/keys):
- Key rotation policy:
- AuthN/AuthZ:
- Network segmentation requirements:
- Secure storage (TPM/HSM/etc):

## 9) Operations
- Manual override / kill switch:
- Local UI/diagnostics:
- Log retention period:
- Firmware update method:
- Rollback method:

## 10) Compliance + Safety
- Required certifications (UL/IEC/CE):
- Safety case reference:
- Incident response contacts:

