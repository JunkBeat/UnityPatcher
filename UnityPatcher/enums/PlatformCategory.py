from enum import Enum

from UnityPy.enums import BuildTarget as BT


class PlatformCategory(Enum):
    WebGL = "webgl"
    Windows = "win"
    Linux = "linux"
    OSX = "osx"


PLATFORM_MAPPING = {
    PlatformCategory.WebGL: [BT.WebGL],
    PlatformCategory.Windows: [BT.StandaloneWindows, BT.StandaloneWindows64],
    PlatformCategory.Linux: [
        BT.StandaloneLinux,
        BT.StandaloneLinux64,
        BT.StandaloneLinuxUniversal,
    ],
    PlatformCategory.OSX: [
        BT.StandaloneOSX,
        BT.StandaloneOSXIntel,
        BT.StandaloneOSXIntel64,
        BT.StandaloneOSXPPC,
    ],
}
