# Jenkins Integration

## Exit codes

Plan runner (`hb plan run`):
- 0 = PASS
- 1 = PASS_WITH_DRIFT
- 2 = FAIL
- 3 = NO_TEST / error

## Example pipeline

```
pipeline {
  agent any
  stages {
    stage('Run Plan') {
      steps {
        sh 'bin/hb plan run plans/example_plan.yaml --out plan_output'
        archiveArtifacts artifacts: 'plan_output/**', fingerprint: true
      }
      post {
        success { echo 'PASS' }
        unstable { echo 'PASS_WITH_DRIFT' }
        failure { echo 'FAIL/NO_TEST' }
      }
    }
  }
}
```

## Adapter usage

Use the Jenkins workspace adapter to export an artifact directory from a build workspace:

```
python - <<'PY'
from hb_core.adapters import JenkinsWorkspaceAdapter

adapter = JenkinsWorkspaceAdapter()
adapter.export(workspace_dir=".", out_dir="artifact_out", artifact_subdir="artifact_dir")
print("exported to artifact_out")
PY
```

If you want PASS_WITH_DRIFT to fail the build, add:
```
sh 'bin/hb plan run plans/example_plan.yaml --out plan_output || exit $?'
```
