import os
import shutil

from hb_core.adapters.base import ArtifactAdapter
from hb_core.artifact import validate_artifact_dir


class FilesystemAdapter(ArtifactAdapter):
    name = "filesystem"

    def export(self, source_dir, out_dir):
        if not os.path.isdir(source_dir):
            raise ValueError(f"source_dir not found: {source_dir}")
        os.makedirs(out_dir, exist_ok=True)
        for name in os.listdir(source_dir):
            src = os.path.join(source_dir, name)
            dst = os.path.join(out_dir, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        validate_artifact_dir(out_dir)
        return out_dir
