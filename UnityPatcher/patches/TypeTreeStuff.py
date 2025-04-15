from ctypes import c_uint32
from typing import Optional

from UnityPy.exceptions import TypeTreeError
from UnityPy.files import ObjectReader
from UnityPy.helpers import TypeTreeHelper
from UnityPy.streams import EndianBinaryReader


def _ObjectReader_trim_nodes(_: ObjectReader, node_name: str, nodes: list):
    try:
        i = next(i for i, node in enumerate(nodes) if node.m_Name == node_name)
        return nodes[: i + 1]
    except StopIteration:
        return nodes


def _ObjectReader_read_trimed_typetree(
    self: ObjectReader, end_node_name: str, nodes: list = None
) -> Optional[dict]:
    self.reset()
    nodes = self.get_typetree_nodes(nodes)
    # Trimming nodes to speed up
    trimed_nodes = self.trim_nodes(end_node_name, nodes)
    if len(nodes) > len(trimed_nodes):
        return TypeTreeHelper.read_typetree(trimed_nodes, self, ignore_size=True)

    return TypeTreeHelper.read_typetree(nodes, self)


def _TypeTreeHelper_read_typetree(nodes, reader, ignore_size=False) -> dict:
    """Reads the typetree of the object contained in the reader via the node list.

    Parameters
    ----------
    nodes : list
        List of nodes/nodes
    reader : EndianBinaryReader
        Reader of the object to be parsed

    Returns
    -------
    dict
        The parsed typtree
    """
    reader.reset()

    nodes = TypeTreeHelper.check_nodes(nodes)

    if TypeTreeHelper.read_typetree_c:
        return TypeTreeHelper.read_typetree_c(
            nodes, reader.read_bytes(reader.byte_size), reader.endian
        )

    obj = TypeTreeHelper.read_value(nodes, reader, c_uint32(0))

    if not ignore_size:
        read = reader.Position - reader.byte_start
        if read != reader.byte_size:
            raise TypeTreeError(
                f"Error while read type, read {read} bytes but expected {reader.byte_size} bytes",
                nodes,
            )

    return obj


def _EndianBinaryReader_reset(self):
    self.Position = self.byte_start


def _ObjectReader_read_typetree(
    self: ObjectReader, nodes: list = None, wrap: bool = False
) -> dict:
    if not self.data:
        return self._read_typetree(nodes, wrap)

    # Read current typetree data
    re_reader = EndianBinaryReader(self.data, self.reader.endian)
    re_reader.byte_size = re_reader.Length
    re_reader.byte_start = 0

    if self.byte_start % 4 != 0:
        raise ValueError("Data alignment issue: byte_start is not aligned to 4 bytes")

    return TypeTreeHelper.read_typetree(self.get_typetree_nodes(), re_reader)


# Implementing reading of trimed typetree
ObjectReader.trim_nodes = _ObjectReader_trim_nodes
ObjectReader.read_trimed_typetree = _ObjectReader_read_trimed_typetree
TypeTreeHelper.read_typetree = _TypeTreeHelper_read_typetree

# Implementing reading up-to-date dumps
EndianBinaryReader.reset = _EndianBinaryReader_reset
ObjectReader._read_typetree = ObjectReader.read_typetree  # backup
ObjectReader.read_typetree = _ObjectReader_read_typetree
