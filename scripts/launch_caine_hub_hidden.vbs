Set shell = CreateObject("WScript.Shell")
command = """" & Replace(WScript.ScriptFullName, "launch_caine_hub_hidden.vbs", "launch_caine_hub.bat") & """"
shell.Run command, 0, False
