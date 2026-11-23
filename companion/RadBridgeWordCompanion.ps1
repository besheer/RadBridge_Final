﻿<#
.SYNOPSIS
    RadBridge Microsoft Word Direct Companion (Windows Native)
    Direct 1-Click Launch, Real-Time Sync, and Anti-Mixup Safe Finalization.
#>

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [string]$LaunchUri = ""
)

if ([string]::IsNullOrWhiteSpace($LaunchUri) -and $args.Count -gt 0) {
    $LaunchUri = $args[0]
}

# Enable modern TLS (1.2 and 1.3) and bypass certificate warnings
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = {$true}

# Load Windows Forms & Drawing assemblies
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Parse-UriParams($raw) {
    $params = @{}
    if ([string]::IsNullOrWhiteSpace($raw)) { return $params }
    
    $clean = $raw.Trim().Trim('"').Trim("'")
    if ($clean.StartsWith("radbridge-word://")) {
        $clean = $clean.Substring(17)
    }
    if ($clean.StartsWith("open?")) {
        $clean = $clean.Substring(5)
    } elseif ($clean.StartsWith("open/?")) {
        $clean = $clean.Substring(6)
    } elseif ($clean.StartsWith("?")) {
        $clean = $clean.Substring(1)
    }
    
    if ($clean.Contains('?')) {
        $clean = $clean.Substring($clean.IndexOf('?') + 1)
    }
    
    $pairs = $clean.Split('&')
    foreach ($p in $pairs) {
        if ($p.Contains('=')) {
            $kv = $p.Split('=', 2)
            $key = [System.Net.WebUtility]::UrlDecode($kv[0].Trim())
            $val = [System.Net.WebUtility]::UrlDecode($kv[1].Trim())
            $params[$key] = $val
        }
    }
    return $params
}

$argsMap = Parse-UriParams $LaunchUri

$server = if ($argsMap.ContainsKey('server')) { $argsMap['server'].TrimEnd('/') } else { 'https://airscan.dynu.net' }
$orderId = if ($argsMap.ContainsKey('order_id')) { [int]$argsMap['order_id'] } else { 0 }
$accession = if ($argsMap.ContainsKey('accession')) { $argsMap['accession'] } else { '' }
$patientName = if ($argsMap.ContainsKey('patient_name')) { $argsMap['patient_name'] } else { 'Unknown Patient' }
$patientId = if ($argsMap.ContainsKey('patient_id')) { $argsMap['patient_id'] } else { '' }
$study = if ($argsMap.ContainsKey('study')) { $argsMap['study'] } else { '' }
$token = if ($argsMap.ContainsKey('token')) { $argsMap['token'] } else { '' }
$versionNo = if ($argsMap.ContainsKey('version_no')) { [int]$argsMap['version_no'] } else { 0 }
$status = if ($argsMap.ContainsKey('status')) { $argsMap['status'] } else { 'DRAFT' }

if ($orderId -le 0 -or [string]::IsNullOrWhiteSpace($token)) {
    [System.Windows.Forms.MessageBox]::Show(
        "لم يتم تمرير بيانات الحالة بشكل صحيح من المتصفح.`nيرجى فتح الحالة من واجهة RadBridge ثم الضغط على زر Word المباشر.",
        "RadBridge Word Companion",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Warning
    )
    exit 1
}

# ----------------------------------------------------
# 1. STRICT ISOLATED CLIENT WORKSPACE (Zero-Mixup)
# ----------------------------------------------------
$sessionGuid = [Guid]::NewGuid().ToString('N')
$workDir = Join-Path $env:LOCALAPPDATA "RadBridge\Sessions\Order_${orderId}_${accession}_${sessionGuid}"
New-Item -ItemType Directory -Force -Path $workDir | Out-Null

$cleanName = [regex]::Replace($patientName, '[^\w\u0600-\u06FF.-]', '_')
$localDocx = Join-Path $workDir "${cleanName}_${accession}.docx"

# Candidate servers: try the passed server first, fallback to https://airscan.dynu.net
$serversToTry = @($server)
if ($server -ne 'https://airscan.dynu.net') {
    $serversToTry += 'https://airscan.dynu.net'
}

$downloadSucceeded = $false
$lastError = ""
$script:activeServer = $server

foreach ($cand in $serversToTry) {
    try {
        $downloadUrl = "$cand/api/reports/$orderId/word-direct-file?token=$token"
        $wc = New-Object System.Net.WebClient
        $wc.Headers.Add("User-Agent", "RadBridgeWordCompanion/1.0")
        $wc.DownloadFile($downloadUrl, $localDocx)
        $wc.Dispose()
        if (Test-Path $localDocx) {
            $downloadSucceeded = $true
            $script:activeServer = $cand
            break
        }
    } catch {
        $lastError = $_.Exception.Message
    }
}

if (-not $downloadSucceeded) {
    [System.Windows.Forms.MessageBox]::Show(
        "فشل تنزيل ملف التقرير من السيرفر:`nالرابط: $downloadUrl`nالسبب: $lastError`n`nيرجى التأكد من اتصال الإنترنت.",
        "خطأ في الاتصال بالخادم",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    )
    Remove-Item -Recurse -Force -Path $workDir -ErrorAction SilentlyContinue
    exit 1
}

# ----------------------------------------------------
# 2. OPEN MICROSOFT WORD VIA COM
# ----------------------------------------------------
$WordApp = $null
$Doc = $null
try {
    $WordApp = New-Object -ComObject Word.Application
    $WordApp.Visible = $true
    $Doc = $WordApp.Documents.Open($localDocx)
    $WordApp.Activate()
} catch {
    Start-Process $localDocx
}

# ----------------------------------------------------
# 3. FLOATING CLINICAL HUD / TOOLBAR (Dark Slate Theme)
# ----------------------------------------------------
$form = New-Object System.Windows.Forms.Form
$form.Text = "RadBridge Reporter — $patientName"
$form.Size = New-Object System.Drawing.Size(530, 240)
$form.StartPosition = "Manual"
$form.FormBorderStyle = "FixedToolWindow"
$form.TopMost = $true
$form.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#0b1322")
$form.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#f8fafc")
$form.Font = New-Object System.Drawing.Font("Segoe UI", 9)

# Position at top-right of screen
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.Location = New-Object System.Drawing.Point(($screen.Right - 550), 30)

# Header App Title
$lblApp = New-Object System.Windows.Forms.Label
$lblApp.Text = "🩺 RadBridge Direct Word Reporter"
$lblApp.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$lblApp.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#38bdf8")
$lblApp.Location = New-Object System.Drawing.Point(16, 10)
$lblApp.Size = New-Object System.Drawing.Size(280, 22)
$form.Controls.Add($lblApp)

# Badge Status
$lblBadge = New-Object System.Windows.Forms.Label
$lblBadge.Text = "$status · v$versionNo"
$lblBadge.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblBadge.TextAlign = "MiddleCenter"
$lblBadge.Size = New-Object System.Drawing.Size(120, 24)
$lblBadge.Location = New-Object System.Drawing.Point(380, 10)
$lblBadge.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#1e293b")
$lblBadge.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#34d399")
$lblBadge.BorderStyle = "FixedSingle"
$form.Controls.Add($lblBadge)

# Patient Card Panel
$panel = New-Object System.Windows.Forms.Panel
$panel.Location = New-Object System.Drawing.Point(16, 38)
$panel.Size = New-Object System.Drawing.Size(484, 76)
$panel.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#131d2f")
$panel.BorderStyle = "FixedSingle"
$form.Controls.Add($panel)

$lblPatient = New-Object System.Windows.Forms.Label
$lblPatient.Text = "👤 $patientName"
$lblPatient.Font = New-Object System.Drawing.Font("Segoe UI", 10.5, [System.Drawing.FontStyle]::Bold)
$lblPatient.ForeColor = [System.Drawing.Color]::White
$lblPatient.Location = New-Object System.Drawing.Point(8, 6)
$lblPatient.Size = New-Object System.Drawing.Size(465, 24)
$panel.Controls.Add($lblPatient)

$lblMeta = New-Object System.Windows.Forms.Label
$lblMeta.Text = "🆔 $patientId   |   📋 Acc: $accession   |   🔬 $study"
$lblMeta.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$lblMeta.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#94a3b8")
$lblMeta.Location = New-Object System.Drawing.Point(8, 30)
$lblMeta.Size = New-Object System.Drawing.Size(465, 20)
$panel.Controls.Add($lblMeta)

$lblSafetyNote = New-Object System.Windows.Forms.Label
$lblSafetyNote.Text = "🛡️ نظام الحماية مفعل: يتم التحقق من بيانات المريض عند الحفظ تلقائياً لمنع أي اختلاط."
$lblSafetyNote.Font = New-Object System.Drawing.Font("Segoe UI", 7.5)
$lblSafetyNote.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#64748b")
$lblSafetyNote.Location = New-Object System.Drawing.Point(8, 52)
$lblSafetyNote.Size = New-Object System.Drawing.Size(465, 18)
$panel.Controls.Add($lblSafetyNote)

# Action Buttons
$btnDraft = New-Object System.Windows.Forms.Button
$btnDraft.Text = "💾 حفظ مسودة (Draft)"
$btnDraft.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$btnDraft.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#1d4ed8")
$btnDraft.ForeColor = [System.Drawing.Color]::White
$btnDraft.FlatStyle = "Flat"
$btnDraft.Location = New-Object System.Drawing.Point(16, 122)
$btnDraft.Size = New-Object System.Drawing.Size(155, 36)
$form.Controls.Add($btnDraft)

$btnVerify = New-Object System.Windows.Forms.Button
$btnVerify.Text = "🩺 مراجعة (Verify)"
$btnVerify.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$btnVerify.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#0f766e")
$btnVerify.ForeColor = [System.Drawing.Color]::White
$btnVerify.FlatStyle = "Flat"
$btnVerify.Location = New-Object System.Drawing.Point(180, 122)
$btnVerify.Size = New-Object System.Drawing.Size(155, 36)
$form.Controls.Add($btnVerify)

$btnFinalize = New-Object System.Windows.Forms.Button
$btnFinalize.Text = "🔒 اعتماد نهائي (Finalize)"
$btnFinalize.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$btnFinalize.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#991b1b")
$btnFinalize.ForeColor = [System.Drawing.Color]::White
$btnFinalize.FlatStyle = "Flat"
$btnFinalize.Location = New-Object System.Drawing.Point(344, 122)
$btnFinalize.Size = New-Object System.Drawing.Size(155, 36)
$form.Controls.Add($btnFinalize)

# Status Log Bar
$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "🟢 متصل بالخادم · جاهز للكتابة والحفظ"
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$lblStatus.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#38bdf8")
$lblStatus.Location = New-Object System.Drawing.Point(16, 168)
$lblStatus.Size = New-Object System.Drawing.Size(484, 22)
$form.Controls.Add($lblStatus)

# ----------------------------------------------------
# 4. MULTIPART UPLOAD FUNCTION
# ----------------------------------------------------
function Sync-CaseReport([string]$actionName) {
    if ($Doc -ne $null) {
        try { $Doc.Save() } catch {}
    }

    $lblStatus.Text = "⏳ جاري إرسال البيانات والتحقق من أمان الملف..."
    $lblStatus.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#fbbf24")
    $form.Refresh()

    $boundary = [System.Guid]::NewGuid().ToString()
    $LF = "`r`n"
    $syncUrl = "$($script:activeServer)/api/reports/$orderId/word-direct-sync"

    try {
        # Read bytes safely while Word has the file open (FileShare.ReadWrite)
        [byte[]]$fileBytes = $null
        try {
            $fs = New-Object System.IO.FileStream($localDocx, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            $fileBytes = New-Object byte[] $fs.Length
            $fs.Read($fileBytes, 0, $fs.Length) | Out-Null
            $fs.Close()
            $fs.Dispose()
        } catch {
            $tmpCopy = Join-Path $env:TEMP ('rb_' + [System.Guid]::NewGuid().ToString('N') + '.docx')
            $srcStream = New-Object System.IO.FileStream($localDocx, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            $dstStream = New-Object System.IO.FileStream($tmpCopy, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
            $srcStream.CopyTo($dstStream)
            $srcStream.Close()
            $srcStream.Dispose()
            $dstStream.Close()
            $dstStream.Dispose()
            $fileBytes = [System.IO.File]::ReadAllBytes($tmpCopy)
            Remove-Item $tmpCopy -Force -ErrorAction SilentlyContinue
        }

        if ($fileBytes -eq $null -or $fileBytes.Length -eq 0) {
            throw "تعذر قراءة محتوى ملف الوورد (حجم الملف غير صالح)"
        }
        $enc = [System.Text.Encoding]::UTF8

        $bodyStream = New-Object System.IO.MemoryStream
        $writer = New-Object System.IO.StreamWriter($bodyStream, $enc)

        $fields = @{
            'token' = $token
            'action' = $actionName
            'base_version_no' = $versionNo.ToString()
            'commit_id' = [System.Guid]::NewGuid().ToString('N')
        }

        foreach ($k in $fields.Keys) {
            $writer.Write("--$boundary$LF")
            $writer.Write("Content-Disposition: form-data; name=`"$k`"$LF$LF")
            $writer.Write("$($fields[$k])$LF")
        }

        $fileName = [System.IO.Path]::GetFileName($localDocx)
        $writer.Write("--$boundary$LF")
        $writer.Write("Content-Disposition: form-data; name=`"document`"; filename=`"$fileName`"$LF")
        $writer.Write("Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document$LF$LF")
        $writer.Flush()

        $bodyStream.Write($fileBytes, 0, $fileBytes.Length)
        
        $writer.Write("$LF--$boundary--$LF")
        $writer.Flush()

        $bodyBytes = $bodyStream.ToArray()
        $writer.Dispose()
        $bodyStream.Dispose()

        $req = [System.Net.HttpWebRequest]::Create($syncUrl)
        $req.Method = "POST"
        $req.UserAgent = "RadBridgeWordCompanion/1.0"
        $req.ContentType = "multipart/form-data; boundary=$boundary"
        $req.ContentLength = $bodyBytes.Length
        $req.Timeout = 40000
        $req.ServerCertificateValidationCallback = {$true}

        $reqStream = $req.GetRequestStream()
        $reqStream.Write($bodyBytes, 0, $bodyBytes.Length)
        $reqStream.Close()

        $resp = $req.GetResponse()
        $respStream = $resp.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($respStream)
        $jsonRaw = $reader.ReadToEnd()
        $reader.Close()
        $resp.Close()

        $result = ConvertFrom-Json $jsonRaw

        if ($result.ok) {
            $script:versionNo = [int]$result.version_no
            $script:status = $result.status
            $lblBadge.Text = "$($result.status) · v$($result.version_no)"
            
            if ($actionName -eq 'FINAL') {
                $lblBadge.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#064e3b")
                $lblBadge.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#6ee7b7")
                $lblStatus.Text = "✅ تم الاعتماد النهائي بنجاح وتم قفل التقرير!"
                $lblStatus.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#34d399")
                
                [System.Windows.Forms.MessageBox]::Show(
                    "✅ تم الاعتماد النهائي للتقرير الطبي بنجاح!`nتم توليد ملف الـ PDF الرسمي وحفظه في الأرشيف وقفل الحالة.",
                    "تم الاعتماد بنجاح",
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information
                )
                
                if ($Doc -ne $null) { try { $Doc.Close([ref][Microsoft.Office.Interop.Word.WdSaveOptions]::wdDoNotSaveChanges) } catch {} }
                $form.Close()
                return
            }

            if ($actionName -eq 'VERIFY') {
                $lblBadge.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#134e4a")
                $lblBadge.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#5eead4")
                $lblStatus.Text = "🩺 تم توثيق ومراجعة التقرير بنجاح (نسخة $script:versionNo)."
                $lblStatus.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#2dd4bf")
                return
            }

            $lblStatus.Text = "💾 تم حفظ المسودة (نسخة $script:versionNo) بنجاح على السيرفر."
            $lblStatus.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#38bdf8")
        }

    } catch [System.Net.WebException] {
        $errResp = $_.Exception.Response
        if ($errResp -ne $null) {
            $stream = $errResp.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $errJson = $reader.ReadToEnd()
            $reader.Close()
            
            try {
                $errObj = ConvertFrom-Json $errJson
                if ($errObj.error -eq 'PATIENT_MISMATCH') {
                    $lblStatus.Text = "❌ خطأ أمان: عدم تطابق بيانات المريض!"
                    $lblStatus.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#f87171")
                    
                    [System.Windows.Forms.MessageBox]::Show(
                        "⚠️ تنبيه أمان طبي عالي (ZERO-MIXUP VIOLATION):`n`nبيانات المريض في المستند لا تتطابق مع المريض المفتوح في السيستم!`n`nالمتوقع: PID=$($errObj.expected_patient_id) | Acc=$($errObj.expected_accession)`nالموجود: PID=$($errObj.found_patient_id) | Acc=$($errObj.found_accession)`n`nتم حظر الحفظ فوراً لحماية بيانات المرضى من الاختلاط.",
                        "حظر الحفظ - عدم تطابق بيانات المريض",
                        [System.Windows.Forms.MessageBoxButtons]::OK,
                        [System.Windows.Forms.MessageBoxIcon]::Stop
                    )
                    return
                }
                $lblStatus.Text = "❌ فشل: $($errObj.message)"
                $lblStatus.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#f87171")
                return
            } catch {}
        }
        $lblStatus.Text = "❌ خطأ في الاتصال: $($_.Exception.Message)"
        $lblStatus.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#f87171")
    } catch {
        $lblStatus.Text = "❌ خطأ: $($_.Exception.Message)"
        $lblStatus.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#f87171")
    }
}

# ----------------------------------------------------
# 5. BUTTON EVENT HANDLERS
# ----------------------------------------------------
$btnDraft.Add_Click({
    Sync-CaseReport "DRAFT"
})

$btnVerify.Add_Click({
    $confirm = [System.Windows.Forms.MessageBox]::Show(
        "تأكيد مراجعة وتوثيق التقرير (Verify)؟`n`nالمريض: $patientName`nرقم الفحص: $accession",
        "تأكيد مراجعة التقرير",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($confirm -eq [System.Windows.Forms.DialogResult]::Yes) {
        Sync-CaseReport "VERIFY"
    }
})

$btnFinalize.Add_Click({
    $confirm = [System.Windows.Forms.MessageBox]::Show(
        "⚠️ هل أنت متأكد من الاعتماد النهائي للتقرير الطبي؟`n`nالمريض: $patientName`nالفحص: $study`n`nتنبيه: بعد الاعتماد النهائي سيتم قفل التقرير وتوليد ملف PDF الرسمي وإرساله للمريض والأرشيف ولن يمكن تعديل التقرير مباشرة.",
        "تأكيد الاعتماد النهائي للتقرير",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Warning
    )
    if ($confirm -eq [System.Windows.Forms.DialogResult]::Yes) {
        Sync-CaseReport "FINAL"
    }
})

$form.Add_FormClosing({
    param($s, $e)
    if ($Doc -ne $null) {
        try {
            if (-not $Doc.Saved -and $script:status -ne 'FINAL') {
                $ans = [System.Windows.Forms.MessageBox]::Show(
                    "هل تود حفظ آخر تعديلاتك كمسودة قبل إغلاق نافذة RadBridge؟",
                    "حفظ التغييرات",
                    [System.Windows.Forms.MessageBoxButtons]::YesNoCancel,
                    [System.Windows.Forms.MessageBoxIcon]::Question
                )
                if ($ans -eq [System.Windows.Forms.DialogResult]::Yes) {
                    Sync-CaseReport "DRAFT"
                } elseif ($ans -eq [System.Windows.Forms.DialogResult]::Cancel) {
                    $e.Cancel = $true
                    return
                }
            }
        } catch {}
    }
    Remove-Item -Recurse -Force -Path $workDir -ErrorAction SilentlyContinue
})

[System.Windows.Forms.Application]::Run($form)
