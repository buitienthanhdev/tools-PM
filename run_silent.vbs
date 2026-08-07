Set WinScriptHost = CreateObject("WScript.Shell")
WinScriptHost.Run "cmd /c cd /d ""d:\tools PM"" && ""C:\Users\TIEN THANH\.conda\envs\paint-ai\python.exe"" watchdog.py", 0, False
