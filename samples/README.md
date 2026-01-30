# Sample Actions

Validate sample actions against guardrails:

```
python tools/guardrails_check.py --action samples/action_rate_limit_example.json
python tools/guardrails_check.py --action samples/action_safe_mode_example.json
python tools/guardrails_check.py --action samples/action_restart_example.json
```

Guardrails config lives at `configs/guardrails.yaml`.
