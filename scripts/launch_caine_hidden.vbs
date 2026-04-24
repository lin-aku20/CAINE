Set shell = CreateObject("WScript.Shell")
currentDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
command = Chr(34) & currentDir & "\.venv\Scripts\pythonw.exe" & Chr(34) & " " & Chr(34) & currentDir & "\main.py" & Chr(34)
shell.CurrentDirectory = currentDir
shell.Run command, 0, False
