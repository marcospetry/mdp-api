param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Assert-Equal($actual, $expected, $label) {
    if ($actual -ne $expected) {
        throw "$label: esperado=$expected encontrado=$actual"
    }
    Write-Host "OK - $label = $actual"
}

Write-Host "MDP API - Smoke Test CRUD Diagnostico"
$health = Invoke-RestMethod "$BaseUrl/api/health"
Write-Host "OK - health versão $($health.version)"

$categorias = Invoke-RestMethod "$BaseUrl/api/diagnostico/categorias"
Assert-Equal $categorias.Count 8 "categorias"

$perguntas = Invoke-RestMethod "$BaseUrl/api/diagnostico/perguntas"
Assert-Equal $perguntas.Count 25 "perguntas"

$pf001 = $perguntas | Where-Object { $_.codigo -eq "PF001" }
if (-not $pf001) { throw "PF001 não encontrada" }
Write-Host "OK - PF001 encontrada ($($pf001.id))"

$opcoes = Invoke-RestMethod "$BaseUrl/api/diagnostico/perguntas/$($pf001.id)/opcoes"
Assert-Equal $opcoes.Count 3 "opções PF001"

$rotulos = @($opcoes | ForEach-Object { $_.rotulo })
foreach ($esperado in @("Sim", "Parcialmente", "Não")) {
    if ($rotulos -notcontains $esperado) { throw "Opção esperada não encontrada: $esperado" }
}
Write-Host "OK - opções PF001: Sim / Parcialmente / Não"

Write-Host "SMOKE TEST OK"
