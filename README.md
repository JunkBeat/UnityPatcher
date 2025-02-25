# UnityPatcher
**UnityPatcher**, or simply **Patcher**, is a command-line tool for patching assets in Unity files. It is based on UnityPy.

![image](https://github.com/user-attachments/assets/a0dbf7f9-e270-4f0b-93c9-4e4e9f6a9c15)

### **Features**:
- Compatible with asset types such as `Texture2D`, `TextAsset`, `AudioClip`, `VideoClip`, `MonoBehaviour`, and more.  
- Supports extracting `MonoBehaviour` dumps for Unity versions up to ~2021.  
- Edit bundles directly without the need to unpack CAB files.  
- Repack bundles using the original compression method.  
- Export assets in **converted**, **raw**, or **JSON dump** formats.  
- The import process prioritizes the dump first, followed by the associated converted files.  

### **Key Advantages**:
Everything is done in just a few clicks, and the commands are very simple. Folder structure is not enforced because all essential information about the exported assets is embedded in the file names. This allows you to organize the files in any way you prefer.

### **Requirement**
- .NET Framework - for typetree generation and texture compression.
- ffmpeg, downloaded and added to PATH - for video encoding (not necessary if you don't use this option).

### **Important** 
- You should pack only edited files.
- Patcher is designed for Unity games made for **Windows**. Compatibility with other platforms is not guaranteed.
- The specified unity folder should not contain files from different games or with the same names, otherwise the packing will not be done correctly. You can use the `--blacklist` option to add specific folders and paths to the blacklist.
- If you have problems loading files while patching ("Can't load file"), you can try loading the entire game folder instead of using partial loading `--load_all`.
- If certain files are not imported, check if smart patching is enabled. Try disabling it and try again. Check if type filters are enabled.
- If your computer isn't very powerful and you're experiencing low performance with the program, it might be because you have too many programs open. You can try reducing the number of threads with the `--threads` option to see if that improves the situation.
- MonoBehaviour may require additional dependencies, such as globalgamemanagers. If you encounter the error "Failed to read typetree":
  1. Scroll through the log above and make sure there are no lines saying "Typetree was not generated because Managed was not in the game folder". If your game doesn't have this folder, use [Il2CppDumper](https://github.com/Perfare/Il2CppDumper/releases) to generate dummy libraries using global-metadata.dat and GameAssembly.dll. Rename the resulting folder to Managed and place it in the game's Data folder.
  2. If the previous step did not help, some dependencies may be missing. Make sure that there are no lines like "Can't load dependency" in the log. The missing files should be placed in the game folder. "Can't load possible dependency" are just hypothetical dependencies.  
- Patcher is still under development. Please, if you encounter a bug, report it [here](https://github.com/JunkBeat/UnityPatcher/issues). But first, make sure you've done everything correctly!

### **Commands**
At the moment UnityPatcher supports 3 commands (pack, unpack, search). You can find out the full list of options by calling one of the following commands in the command line:
- `Patcher pack -h`
- `Patcher unpack -h`
- `Patcher search -h`

### **Examples of usage**
- `Patcher unpack --texture -c Text -i Game_Data -o ExtractedAssets`
- `Patcher pack Patches --outsamedir`
- `Patcher search "example text" --export`

### **Download**
[Latest releases](https://github.com/JunkBeat/UnityPatcher/releases)

### **Support**
Patcher is a solo project and an attempt to make a convenient modding utility available to everyone. It takes a lot of time to develop, so if you want to support me, you can donate via Paypal - pmwavex@gmail.com. Thank you!

<img src="https://visit-counter.vercel.app/counter.png?page=https%3A%2F%2Fgithub.com%2FJunkBeat%2FUnityPatcher&s=40&c=00ff00&bg=00000000&no=2&ff=electrolize&tb=&ta=" alt="visits">
