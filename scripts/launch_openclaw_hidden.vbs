Set shell = CreateObject("WScript.Shell")
ollama = """C:\Users\melin\AppData\Local\Programs\Ollama\ollama.exe"""
shell.Run ollama, 0, False
WScript.Sleep 4000
command = """" & shell.ExpandEnvironmentStrings("%APPDATA%") & "\npm\openclaw.cmd"" gateway run --allow-unconfigured --bind loopback --port 18789"
shell.Run command, 0, False
