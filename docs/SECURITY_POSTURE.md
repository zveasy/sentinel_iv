# Security Posture (Field Deployment v1)

- **Local-only services**: bind to 127.0.0.1 unless explicitly approved.
- **Secrets management**: no secrets in repo; use environment variables or protected files.
- **Key rotation**: rotate signing/encryption keys per deployment cadence.
- **Access control**: optional token for feedback service (`HB_FEEDBACK_TOKEN`).
- **Data protection**: artifact hashing + optional encryption; restricted file permissions (0600).
- **Network segmentation**: isolate HB host from production control networks; allow only required telemetry ingress/egress.
