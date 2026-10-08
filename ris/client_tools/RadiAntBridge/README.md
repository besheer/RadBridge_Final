# RadBridge RadiAnt launcher (Windows)

Install and license RadiAnt separately: https://www.radiantviewer.com/download/ . This bundle does not include RadiAnt or a license. The documented RadiAnt command line opens a local ZIP; a hosted ZIP must first be downloaded.

Extract this bundle and run from Windows PowerShell, using your installation path:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-RadiAntBridge.ps1 -ServerUrl https://rispacs.radbridges.com -RadiAntPath "C:\Program Files\RadiAntViewer64bit\RadiAntViewer.exe"
```

Registration is for the current Windows user only. Return to the case in RadBridge, choose RadiAnt, and click Open RadiAnt. Allow the browser to launch RadBridge's handler. No PACS credentials are installed. Access links expire after 20 minutes and recheck the issuing doctor's current case permissions and image identity. Refresh the case page to renew access.

Downloads are stored in `%LOCALAPPDATA%\RadBridge\RadiAntBridge\Cache`. These are clinical copies, persist after link expiry, and must be managed under your workstation retention policy. Do not delete files while RadiAnt is using them. A manual Download ZIP option is available if the launcher is not installed.

The launcher accepts only the configured HTTPS origin and dedicated study archive path, refuses redirects, and checks the server SHA-256 before opening the ZIP. It never uses a shell command supplied by a URL. No automatic patient correction or unrestricted PACS query/retrieve is provided.

To unregister, remove only `HKCU:\Software\Classes\radbridge-radiant`. Retain or remove the local cache separately according to your policy. Changing the RIS origin requires running the installer again.

Official protocol/command documentation: https://www.radiantviewer.com/dicom-viewer-manual/command-line_arguments.html
