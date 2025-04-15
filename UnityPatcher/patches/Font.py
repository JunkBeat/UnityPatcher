from UnityPy.classes import Font

from helpers import GeneralHelper


def _Font_set_font(self: Font, file: str):
    if not file:
        raise ValueError("Font file not provided")

    magic = GeneralHelper.read_binary_file(file, length=4)

    if magic not in [b"OTTO", b"\x00\x01\x00\x00"]:
        raise ValueError(f"Incorrect font format: {file}. Expected ttf/otf")

    font = GeneralHelper.read_binary_file(file)
    self.m_FontData = font


def _Font_save_via_tree(self: Font):
    tree = self.read_typetree()

    if not tree:
        raise Exception("Typetree is None")

    tree["m_FontData"] = self.m_FontData
    tree["m_CharacterRects"] = []  # delete rects
    tree["m_ConvertCase"] = -2  # dynamic characters
    self.reader.save_typetree(tree)


Font.set_font = _Font_set_font
Font.save_via_tree = _Font_save_via_tree
