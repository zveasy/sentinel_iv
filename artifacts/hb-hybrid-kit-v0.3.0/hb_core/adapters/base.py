class ArtifactAdapter:
    name = "base"

    def export(self, **kwargs):
        raise NotImplementedError("adapter must implement export()")
