Set WinScriptHost = CreateObject("WScript.Shell")
WinScriptHost.Run "cmd /c cd /d ""D:\tools PM\tools PM"" && ""D:\tools PM\tools PM\.venv\Scripts\python.exe"" watchdog.py", 0, False
