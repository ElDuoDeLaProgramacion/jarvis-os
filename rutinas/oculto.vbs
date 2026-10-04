' Ejecuta un programa sin abrir ninguna ventana (ni la negra de la terminal).
' Uso: wscript.exe oculto.vbs programa arg1 arg2 ...   (lo usan las tareas de rutinas\instalar-*.ps1)
Set args = WScript.Arguments
linea = ""
For i = 0 To args.Count - 1
    a = args(i)
    If InStr(a, " ") > 0 Then a = Chr(34) & a & Chr(34)
    linea = linea & a & " "
Next
' 0 = ventana oculta; True = espera a que termine (así el Programador ve cuándo acaba).
WScript.Quit CreateObject("WScript.Shell").Run(Trim(linea), 0, True)
