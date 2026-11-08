' WeChat Shop Helper - start backend in the system tray, with NO console window.
' Right-click the tray icon and choose "Exit" to really stop the service.
Option Explicit

Dim sh, fso, base, py, script
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

base = fso.GetParentFolderName(WScript.ScriptFullName)
py = base & "\.venv\Scripts\pythonw.exe"
script = base & "\tray_app.py"

If Not fso.FileExists(py) Then
    MsgBox "pythonw.exe not found:" & vbCrLf & py, 16, "WXSX Helper"
    WScript.Quit 1
End If
If Not fso.FileExists(script) Then
    MsgBox "tray_app.py not found:" & vbCrLf & script, 16, "WXSX Helper"
    WScript.Quit 1
End If

sh.CurrentDirectory = base
' 0 = hidden window, False = do not wait for it to finish
sh.Run """" & py & """ """ & script & """", 0, False
