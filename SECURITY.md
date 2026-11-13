# Security and privacy

Never commit Wi-Fi passwords, API/proxy credentials, family data, recordings or full Flash backups. Update private device configuration over USB; family export excludes service credentials. Revoke exposed keys at the relevant provider and replace them.

TLS certificates are verified. Each service receives only its own Bearer credential; proxy authentication is separate. Idle microphone data is not uploaded and mute disables capture. Providers process active-session content under their own terms.

This version uses replaceable ordinary NVS without secure boot or Flash encryption. Physical access may expose configuration. USB maintenance requires muted standby. Retrieved and stored text is data, never new system instructions.

Use GitHub private vulnerability reporting for reproducible security issues. Do not paste credentials or family data into public issues.
