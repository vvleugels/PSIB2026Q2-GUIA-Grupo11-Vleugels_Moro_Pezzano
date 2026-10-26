' PSIB.vbs - instala PSIB la primera vez y lo abre sin ventana de comandos.
' Doble clic para iniciar. Guardalo junto a gui.py (la misma carpeta que PSIB.bat).
Option Explicit

Dim shell, fso, folder, python, logFile, q, code
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
q = Chr(34)
folder = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
python = folder & "\.venv\Scripts\python.exe"
logFile = folder & "\psib_launch.log"

If Not fso.FileExists(python) Then
    Install
End If
Launch

' Primera ejecucion: crea el entorno e instala las librerias.
' Estos pasos muestran su ventana para que se vea el progreso.
Sub Install()
    shell.Popup "Primera ejecucion: PSIB se va a instalar." & vbCrLf & _
                "Se abrira una ventana con el progreso. Puede tardar unos minutos y necesita internet.", _
                6, "PSIB", 64

    code = shell.Run("cmd /c py -3.12 -m venv .venv", 1, True)
    If code <> 0 Then
        Fail "No se pudo crear el entorno. Instala Python 3.12 de 64 bits desde python.org " & _
             "con ""py launcher"" y ""tcl/tk and IDLE"" tildados.", False
    End If

    code = shell.Run("cmd /c " & q & q & python & q & " -m pip install -r requirements.txt" & q, 1, True)
    If code <> 0 Then
        Fail "Fallo la instalacion de las dependencias. Revisa tu conexion e intenta de nuevo. " & _
             "Si el problema sigue, abri PSIB.bat para ver el detalle del error.", True
    End If
End Sub

' Abre la app sin consola. Sus mensajes se guardan en psib_launch.log;
' si se cierra con error, se muestra el final de ese archivo.
Sub Launch()
    code = shell.Run("cmd /c " & q & q & python & q & " gui.py > " & q & logFile & q & " 2>&1" & q, 0, True)
    If code <> 0 Then
        MsgBox "PSIB se cerro con un error." & vbCrLf & vbCrLf & LastChars(logFile, 900) & _
               vbCrLf & vbCrLf & "Detalle completo en: " & logFile, 16, "PSIB"
    End If
End Sub

' Muestra un error y termina. Si removeEnvironment es True, borra el entorno
' a medio instalar para que el proximo intento empiece de cero.
Sub Fail(message, removeEnvironment)
    If removeEnvironment Then
        If fso.FolderExists(folder & "\.venv") Then
            fso.DeleteFolder folder & "\.venv", True
        End If
    End If
    MsgBox message, 16, "PSIB"
    WScript.Quit 1
End Sub

Function LastChars(path, maxChars)
    Dim text, file
    text = ""
    If fso.FileExists(path) Then
        Set file = fso.OpenTextFile(path, 1)
        If Not file.AtEndOfStream Then text = file.ReadAll
        file.Close
    End If
    If Len(text) > maxChars Then text = "..." & Right(text, maxChars)
    LastChars = text
End Function