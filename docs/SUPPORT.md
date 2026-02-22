# Support

## How to get help

- **Email:** support@sentinel-iv.example.com
- **Portal:** https://support.sentinel-iv.example.com
- **Documentation:** See the `docs/` folder in this kit and the main README.

When opening a support request, please include:

1. **Version:** Output of `./bin/hb --version` or the contents of `VERSION` in the kit.
2. **Support bundle:** A support bundle helps us diagnose issues quickly.

## Generating a support bundle

Run from the kit directory (or with paths to your config and report dir):

```bash
./bin/hb support bundle --out support_bundle.zip
```

Optionally include a specific report directory:

```bash
./bin/hb support bundle --out support_bundle.zip --report-dir /path/to/report_dir
```

Attach `support_bundle.zip` to your support request. The bundle contains configuration, run metadata, and log excerpts—no raw metric data unless you include a report dir that contains it. Do not include sensitive data you are not allowed to share.

## Health check (before contacting support)

Run a quick self-check:

```bash
./bin/hb support health
```

Fix any reported issues (e.g. missing config, DB lock) and try again. If the problem persists, generate a support bundle and contact support with the details above.

---

For your distribution, replace the support email and portal URL above with your actual support contact.
