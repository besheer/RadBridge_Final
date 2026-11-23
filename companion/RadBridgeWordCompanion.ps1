<#
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

$server = if ($argsMap.ContainsKey('server')) { $argsMap['server'].TrimEnd('/') } else { 'http://192.168.100.23:8090' }
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

# Candidate servers: try the passed server first, fallback to LAN IP and public WAN domain
$serversToTry = @()
if (-not [string]::IsNullOrWhiteSpace($server)) {
    $serversToTry += $server.TrimEnd('/')
}
if ($serversToTry -notcontains 'http://192.168.100.23:8090') {
    $serversToTry += 'http://192.168.100.23:8090'
}
if ($serversToTry -notcontains 'https://airscan.dynu.net') {
    $serversToTry += 'https://airscan.dynu.net'
}

$downloadSucceeded = $false
$lastError = ""
$script:activeServer = $serversToTry[0]

foreach ($cand in $serversToTry) {
    try {
        $downloadUrl = "$cand/api/reports/$orderId/word-direct-file?token=$token"
        $req = [System.Net.HttpWebRequest]::Create($downloadUrl)
        $req.Timeout = 6000
        $req.ReadWriteTimeout = 15000
        $req.UserAgent = "RadBridgeWordCompanion/1.0"
        $req.ServerCertificateValidationCallback = { $true }
        
        $resp = $req.GetResponse()
        $respStream = $resp.GetResponseStream()
        $fileStream = New-Object System.IO.FileStream($localDocx, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
        $respStream.CopyTo($fileStream)
        $fileStream.Close()
        $fileStream.Dispose()
        $respStream.Close()
        $respStream.Dispose()
        $resp.Close()
        
        if ((Test-Path $localDocx) -and (Get-Item $localDocx).Length -gt 0) {
            $downloadSucceeded = $true
            $script:activeServer = $cand
            break
        }
    } catch {
        $lastError = $_.Exception.Message
        if (Test-Path $localDocx) { Remove-Item -Force $localDocx -ErrorAction SilentlyContinue }
    }
}

if (-not $downloadSucceeded) {
    [System.Windows.Forms.MessageBox]::Show(
        "فشل تنزيل ملف التقرير من السيرفر:`nالرابط المحاول: $downloadUrl`nالسبب: $lastError`n`nيرجى التأكد من تشغيل السيرفر أو اتصال الإنترنت.",
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

# Position top-right near Word ribbon
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.Location = New-Object System.Drawing.Point(($screen.Right - 550), ($screen.Top + 35))

# Header: Title & Version badge
$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "🗲 RadBridge Direct Word Reporter"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#38bdf8")
$lblTitle.Location = New-Object System.Drawing.Point(16, 12)
$lblTitle.Size = New-Object System.Drawing.Size(320, 24)
$form.Controls.Add($lblTitle)

$lblBadge = New-Object System.Windows.Forms.Label
$lblBadge.Text = "$status · v$versionNo"
$lblBadge.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblBadge.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#93c5fd")
$lblBadge.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#1e293b")
$lblBadge.TextAlign = "MiddleCenter"
$lblBadge.Location = New-Object System.Drawing.Point(395, 12)
$lblBadge.Size = New-Object System.Drawing.Size(105, 22)
$form.Controls.Add($lblBadge)

# Patient Clinical Context Card
$pnlCard = New-Object System.Windows.Forms.Panel
$pnlCard.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#131d31")
$pnlCard.Location = New-Object System.Drawing.Point(16, 42)
$pnlCard.Size = New-Object System.Drawing.Size(484, 70)
$form.Controls.Add($pnlCard)

$lblPatient = New-Object System.Windows.Forms.Label
$lblPatient.Text = "🗎 $patientName"
$lblPatient.Font = New-Object System.Drawing.Font("Segoe UI", 10.5, [System.Drawing.FontStyle]::Bold)
$lblPatient.ForeColor = [System.Drawing.Color]::White
$lblPatient.Location = New-Object System.Drawing.Point(10, 6)
$lblPatient.Size = New-Object System.Drawing.Size(464, 22)
$pnlCard.Controls.Add($lblPatient)

$lblMeta = New-Object System.Windows.Forms.Label
$lblMeta.Text = "🪪 $patientId   |   Acc: $accession   |   $study"
$lblMeta.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$lblMeta.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#94a3b8")
$lblMeta.Location = New-Object System.Drawing.Point(10, 30)
$lblMeta.Size = New-Object System.Drawing.Size(464, 18)
$pnlCard.Controls.Add($lblMeta)

$lblSafety = New-Object System.Windows.Forms.Label
$lblSafety.Text = "🛡 نظام الحماية مفعل: يتم التحقق من بيانات المريض عند الحفظ تلقائياً لمنع أي اختلاط"
$lblSafety.Font = New-Object System.Drawing.Font("Segoe UI", 7.5)
$lblSafety.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#38bdf8")
$lblSafety.Location = New-Object System.Drawing.Point(10, 50)
$lblSafety.Size = New-Object System.Drawing.Size(464, 16)
$pnlCard.Controls.Add($lblSafety)

# Actions Row
$btnDraft = New-Object System.Windows.Forms.Button
$btnDraft.Text = "💾 حفظ مسودة (Draft)"
$btnDraft.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$btnDraft.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#0284c7")
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
        $readSuccess = $false
        for ($retry = 0; $retry -lt 5; $retry++) {
            try {
                $fs = New-Object System.IO.FileStream($localDocx, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
                $fileBytes = New-Object byte[] $fs.Length
                $totalRead = 0
                while ($totalRead -lt $fs.Length) {
                    $read = $fs.Read($fileBytes, $totalRead, $fs.Length - $totalRead)
                    if ($read -le 0) { break }
                    $totalRead += $read
                }
                $fs.Close()
                $fs.Dispose()
                if ($fileBytes -ne $null -and $fileBytes.Length -gt 0) {
                    $readSuccess = $true
                    break
                }
            } catch {
                Start-Sleep -Milliseconds 300
            }
        }

        if (-not $readSuccess -or $fileBytes -eq $null -or $fileBytes.Length -eq 0) {
            throw "تعذر قراءة ملف التقرير أثناء فتحه في الوورد. يرجى الضغط على زر الحفظ (Ctrl+S) داخل Word ثم المحاولة مجدداً."
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
