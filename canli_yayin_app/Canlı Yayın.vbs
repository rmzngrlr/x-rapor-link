Set WshShell = CreateObject("WScript.Shell")
strPath = WScript.ScriptFullName
strPath = Left(strPath, InStrRev(strPath, "\"))
WshShell.Run chr(34) & strPath & "baslat.bat" & Chr(34), 0
Set WshShell = Nothing