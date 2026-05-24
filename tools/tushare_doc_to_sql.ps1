param(
    [string]$OutputPath = "infra/postgres/init/010_tushare_stock_schema.sql"
)

$ErrorActionPreference = "Stop"

$docs = @(
    @{ Group = "basic"; DocId = 25;  FallbackApi = "stock_basic" },
    @{ Group = "basic"; DocId = 329; FallbackApi = $null },
    @{ Group = "basic"; DocId = 26;  FallbackApi = "trade_cal" },
    @{ Group = "basic"; DocId = 397; FallbackApi = $null },
    @{ Group = "basic"; DocId = 423; FallbackApi = $null },
    @{ Group = "basic"; DocId = 398; FallbackApi = $null },
    @{ Group = "basic"; DocId = 100; FallbackApi = "namechange" },
    @{ Group = "basic"; DocId = 112; FallbackApi = "stock_company" },
    @{ Group = "basic"; DocId = 193; FallbackApi = "stk_managers" },
    @{ Group = "basic"; DocId = 194; FallbackApi = "stk_rewards" },
    @{ Group = "basic"; DocId = 375; FallbackApi = $null },
    @{ Group = "basic"; DocId = 123; FallbackApi = "new_share" },
    @{ Group = "basic"; DocId = 262; FallbackApi = $null },

    @{ Group = "quote"; DocId = 27;  FallbackApi = "daily" },
    @{ Group = "quote"; DocId = 372; FallbackApi = $null },
    @{ Group = "quote"; DocId = 370; FallbackApi = $null },
    @{ Group = "quote"; DocId = 374; FallbackApi = $null },
    @{ Group = "quote"; DocId = 457; FallbackApi = $null },
    @{ Group = "quote"; DocId = 144; FallbackApi = "weekly" },
    @{ Group = "quote"; DocId = 145; FallbackApi = "monthly" },
    @{ Group = "quote"; DocId = 146; FallbackApi = "pro_bar" },
    @{ Group = "quote"; DocId = 336; FallbackApi = $null },
    @{ Group = "quote"; DocId = 365; FallbackApi = $null },
    @{ Group = "quote"; DocId = 28;  FallbackApi = "adj_factor" },
    @{ Group = "quote"; DocId = 32;  FallbackApi = "daily_basic" },
    @{ Group = "quote"; DocId = 109; FallbackApi = "pro_bar" },
    @{ Group = "quote"; DocId = 183; FallbackApi = "stk_limit" },
    @{ Group = "quote"; DocId = 214; FallbackApi = "suspend_d" },
    @{ Group = "quote"; DocId = 48;  FallbackApi = "hsgt_top10" },
    @{ Group = "quote"; DocId = 49;  FallbackApi = "ggt_top10" },
    @{ Group = "quote"; DocId = 196; FallbackApi = "ggt_daily" },
    @{ Group = "quote"; DocId = 197; FallbackApi = "ggt_monthly" },
    @{ Group = "quote"; DocId = 255; FallbackApi = $null },

    @{ Group = "finance"; DocId = 33;  FallbackApi = "income" },
    @{ Group = "finance"; DocId = 36;  FallbackApi = "balancesheet" },
    @{ Group = "finance"; DocId = 44;  FallbackApi = "cashflow" },
    @{ Group = "finance"; DocId = 45;  FallbackApi = "forecast" },
    @{ Group = "finance"; DocId = 46;  FallbackApi = "express" },
    @{ Group = "finance"; DocId = 103; FallbackApi = "dividend" },
    @{ Group = "finance"; DocId = 79;  FallbackApi = "fina_indicator" },
    @{ Group = "finance"; DocId = 80;  FallbackApi = "fina_audit" },
    @{ Group = "finance"; DocId = 81;  FallbackApi = "fina_mainbz" },
    @{ Group = "finance"; DocId = 162; FallbackApi = "disclosure_date" }
)

$groupNames = @{
    basic = "basic data"
    quote = "quote data"
    finance = "finance data"
}

function HtmlDecode([string]$Text) {
    return [System.Net.WebUtility]::HtmlDecode(($Text -replace '<[^>]+>', '' -replace '\s+', ' ').Trim())
}

function EscapeSql([string]$Text) {
    if ($null -eq $Text) { return "" }
    return $Text.Replace("'", "''")
}

function ToSnakeCase([string]$Text) {
    $name = $Text.ToLowerInvariant() -replace '[^a-z0-9]+', '_'
    $name = $name.Trim('_')
    if ([string]::IsNullOrWhiteSpace($name)) { return "doc_$([guid]::NewGuid().ToString('N').Substring(0, 8))" }
    return $name
}

function GetPageTitle([string]$Html) {
    $h2 = [regex]::Match($Html, '<h2[^>]*>(.*?)</h2>', 'Singleline,IgnoreCase')
    if ($h2.Success) { return HtmlDecode $h2.Groups[1].Value }
    $title = [regex]::Match($Html, '<title[^>]*>(.*?)</title>', 'Singleline,IgnoreCase')
    if ($title.Success) { return HtmlDecode $title.Groups[1].Value }
    return ""
}

function InferPgType([string]$FieldName, [string]$TushareType) {
    $field = $FieldName.ToLowerInvariant()
    $type = $TushareType.ToLowerInvariant()

    if ($field -match 'date$|cal_date|trade_date|ann_date|end_date|start_date|list_date|delist_date|pay_date|record_date|ex_date|imp_ann_date|setup_date|found_date|due_date|pretrade_date|suspend_date|resume_date') {
        return "date"
    }
    if ($field -match 'time|datetime') { return "text" }
    if ($type -match 'int') { return "integer" }
    if ($type -match 'float|double|number') { return "numeric" }
    if ($type -match 'str|char') { return "text" }
    return "numeric"
}

function GetPrimaryKey([string]$ApiName, [object[]]$Columns) {
    $fields = @($Columns | ForEach-Object { $_.Name })
    $has = {
        param([string]$Name)
        return $fields -contains $Name
    }

    $candidates = @{
        stock_basic = @("ts_code")
        trade_cal = @("exchange", "cal_date")
        namechange = @("ts_code", "start_date", "name")
        stock_company = @("ts_code")
        stk_managers = @("ts_code", "ann_date", "name")
        stk_rewards = @("ts_code", "ann_date", "name", "title")
        new_share = @("ts_code")
        daily = @("ts_code", "trade_date")
        weekly = @("ts_code", "trade_date")
        monthly = @("ts_code", "trade_date")
        pro_bar = @("ts_code", "trade_date")
        adj_factor = @("ts_code", "trade_date")
        daily_basic = @("ts_code", "trade_date")
        stk_limit = @("ts_code", "trade_date")
        suspend_d = @("ts_code", "suspend_date")
        hsgt_top10 = @("trade_date", "ts_code", "market_type")
        ggt_top10 = @("trade_date", "ts_code")
        ggt_daily = @("trade_date")
        ggt_monthly = @("month")
        income = @("ts_code", "ann_date", "end_date", "report_type")
        balancesheet = @("ts_code", "ann_date", "end_date", "report_type")
        cashflow = @("ts_code", "ann_date", "end_date", "report_type")
        forecast = @("ts_code", "ann_date", "end_date")
        express = @("ts_code", "ann_date", "end_date")
        dividend = @("ts_code", "ann_date", "end_date")
        fina_indicator = @("ts_code", "ann_date", "end_date")
        fina_audit = @("ts_code", "ann_date", "end_date")
        fina_mainbz = @("ts_code", "end_date", "bz_item", "bz_code")
        disclosure_date = @("ts_code", "end_date")
    }

    if ($candidates.ContainsKey($ApiName)) {
        $candidate = @($candidates[$ApiName] | Where-Object { & $has $_ })
        if ($candidate.Count -gt 0) { return $candidate }
    }

    if ((& $has "ts_code") -and (& $has "trade_date")) { return @("ts_code", "trade_date") }
    if ((& $has "ts_code") -and (& $has "ann_date") -and (& $has "end_date")) { return @("ts_code", "ann_date", "end_date") }
    if ((& $has "ts_code") -and (& $has "end_date")) { return @("ts_code", "end_date") }
    if (& $has "ts_code") { return @("ts_code") }
    if (& $has "trade_date") { return @("trade_date") }
    return @()
}

function ExtractInterfaceName([string]$Html, [string]$FallbackApi) {
    $patterns = @(
        '接口：\s*([a-zA-Z0-9_]+)',
        '接口名称：\s*([a-zA-Z0-9_]+)',
        '接口:\s*([a-zA-Z0-9_]+)',
        'pro\.([a-zA-Z0-9_]+)\(',
        "query\('([a-zA-Z0-9_]+)'"
    )
    foreach ($pattern in $patterns) {
        $match = [regex]::Match($Html, $pattern)
        if ($match.Success) { return $match.Groups[1].Value }
    }
    return $FallbackApi
}

function ExtractOutputColumns([string]$Html) {
    $outputTitle = [string][char]0x8F93 + [string][char]0x51FA + [string][char]0x53C2 + [string][char]0x6570
    $marker = [regex]::Match($Html, "<(?:strong|h[1-6])[^>]*>\s*$outputTitle\s*</(?:strong|h[1-6])>", 'IgnoreCase')
    if (-not $marker.Success) { return @() }

    $after = $Html.Substring($marker.Index)
    $tableMatch = [regex]::Match($after, '<table>.*?</table>', 'Singleline,IgnoreCase')
    if (-not $tableMatch.Success) { return @() }

    $rows = [regex]::Matches($tableMatch.Value, '<tr>(.*?)</tr>', 'Singleline,IgnoreCase')
    $columns = New-Object System.Collections.Generic.List[object]
    for ($i = 1; $i -lt $rows.Count; $i++) {
        $cells = [regex]::Matches($rows[$i].Groups[1].Value, '<td>(.*?)</td>', 'Singleline,IgnoreCase')
        if ($cells.Count -lt 4) { continue }
        $name = HtmlDecode $cells[0].Groups[1].Value
        if ([string]::IsNullOrWhiteSpace($name) -or $name -match '[^\w]') { continue }
        $typeText = HtmlDecode $cells[1].Groups[1].Value
        $columns.Add([pscustomobject]@{
            Name = $name
            Type = $typeText
            DefaultDisplay = HtmlDecode $cells[2].Groups[1].Value
            Description = HtmlDecode $cells[3].Groups[1].Value
            PgType = InferPgType $name $typeText
        })
    }
    return $columns
}

function WriteTable([System.Text.StringBuilder]$Sql, [hashtable]$Doc, [string]$Title, [string]$ApiName, [object[]]$Columns) {
    $tableName = "tushare.$(ToSnakeCase $ApiName)"
    $pk = @(GetPrimaryKey $ApiName $Columns)
    $fieldNames = @($Columns | ForEach-Object { $_.Name })
    $timeField = @("trade_date", "cal_date", "ann_date", "end_date", "suspend_date") | Where-Object {
        $fieldNames -contains $_
    } | Select-Object -First 1

    [void]$Sql.AppendLine("")
    [void]$Sql.AppendLine("-- $($groupNames[$Doc.Group]) / $Title / https://tushare.pro/document/2?doc_id=$($Doc.DocId)")
    [void]$Sql.AppendLine("CREATE TABLE IF NOT EXISTS $tableName (")

    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($column in $Columns) {
        $line = "    $($column.Name) $($column.PgType)"
        if ($pk -contains $column.Name) { $line += " NOT NULL" }
        $lines.Add($line)
    }
    $lines.Add("    ingested_at timestamptz NOT NULL DEFAULT now()")
    if ($pk.Count -gt 0) {
        $lines.Add("    PRIMARY KEY ($($pk -join ', '))")
    }
    [void]$Sql.AppendLine(($lines -join ",`n"))
    [void]$Sql.AppendLine(");")
    [void]$Sql.AppendLine("COMMENT ON TABLE $tableName IS 'Tushare $($groupNames[$Doc.Group]) - $(EscapeSql $Title), api=$ApiName, doc_id=$($Doc.DocId)';")
    foreach ($column in $Columns) {
        $comment = "$($column.Description) | Tushare type: $($column.Type) | default_display: $($column.DefaultDisplay)"
        [void]$Sql.AppendLine("COMMENT ON COLUMN $tableName.$($column.Name) IS '$(EscapeSql $comment)';")
    }
    [void]$Sql.AppendLine("COMMENT ON COLUMN $tableName.ingested_at IS 'Row ingestion timestamp generated by Fun Stock';")

    if ($timeField) {
        [void]$Sql.AppendLine("CREATE INDEX IF NOT EXISTS ix_tushare_$(ToSnakeCase $ApiName)_$timeField ON $tableName ($timeField DESC);")
    }
    if ($fieldNames -contains "ts_code") {
        [void]$Sql.AppendLine("CREATE INDEX IF NOT EXISTS ix_tushare_$(ToSnakeCase $ApiName)_ts_code ON $tableName (ts_code);")
    }
}

$sql = [System.Text.StringBuilder]::new()
[void]$sql.AppendLine("-- Generated from Tushare official documents on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz').")
[void]$sql.AppendLine("-- Source index: https://tushare.pro/document/2?doc_id=14")
[void]$sql.AppendLine("-- Scope: stock data / basic data, quote data, finance data.")
[void]$sql.AppendLine("")
[void]$sql.AppendLine("CREATE SCHEMA IF NOT EXISTS tushare;")

$summary = New-Object System.Collections.Generic.List[object]

foreach ($doc in $docs) {
    $url = "https://tushare.pro/document/2?doc_id=$($doc.DocId)"
    Write-Host "Fetching $($doc.DocId) ..."
    $html = (Invoke-WebRequest -Uri $url -UseBasicParsing).Content
    $title = GetPageTitle $html
    $apiName = ExtractInterfaceName $html $doc.FallbackApi
    if ([string]::IsNullOrWhiteSpace($apiName)) {
        $apiName = "doc_$($doc.DocId)"
    }
    $columns = @(ExtractOutputColumns $html)
    if ($columns.Count -eq 0) {
        throw "No output columns found for $($doc.DocId)"
    }
    WriteTable $sql $doc $title $apiName $columns
    $summary.Add([pscustomobject]@{
        Group = $doc.Group
        DocId = $doc.DocId
        Title = $title
        Api = $apiName
        Columns = $columns.Count
    })
}

$resolvedOutput = Join-Path (Get-Location) $OutputPath
$parent = Split-Path -Parent $resolvedOutput
if (-not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent | Out-Null
}
[System.IO.File]::WriteAllText($resolvedOutput, $sql.ToString(), [System.Text.UTF8Encoding]::new($false))
$summary | Format-Table -AutoSize
Write-Host "Wrote $resolvedOutput"
