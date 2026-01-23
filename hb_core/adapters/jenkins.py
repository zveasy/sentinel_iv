import os

from hb_core.adapters.base import ArtifactAdapter
from hb_core.adapters.filesystem import FilesystemAdapter


class JenkinsWorkspaceAdapter(ArtifactAdapter):
    name = "jenkins_workspace"

    def export(self, workspace_dir, out_dir, artifact_subdir=None):
        if not os.path.isdir(workspace_dir):
            raise ValueError(f"workspace_dir not found: {workspace_dir}")
        candidates = []
        if artifact_subdir:
            candidates.append(os.path.join(workspace_dir, artifact_subdir))
        candidates.extend(
            [
                workspace_dir,
                os.path.join(workspace_dir, "artifact_dir"),
                os.path.join(workspace_dir, "artifacts", "artifact_dir"),
            ]
        )
        source_dir = None
        for candidate in candidates:
            run_meta = os.path.join(candidate, "run_meta.json")
            metrics = os.path.join(candidate, "metrics.csv")
            if os.path.exists(run_meta) and os.path.exists(metrics):
                source_dir = candidate
                break
        if not source_dir:
            raise ValueError("no artifact_dir found in Jenkins workspace")
        return FilesystemAdapter().export(source_dir=source_dir, out_dir=out_dir)
