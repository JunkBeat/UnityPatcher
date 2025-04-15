from .BaseManager import BaseManager


# For old ~ Unity 2020
class Shader(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.name

    def export(self, path: str = None):
        if self.data.version > (2019,):
            shader = self.data.export()
            if shader:
                dest = self.get_destination_path(self.name, ".txt", path)
                super().save(dest, shader.encode("utf-8"))
        else:
            super().export_dump(path)

    def import_(self, *args):
        raise NotImplementedError("Import is not supported")
