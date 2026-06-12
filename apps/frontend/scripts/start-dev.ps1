# 开发环境一键启动脚本：自动管理 Nginx 生命周期 + 启动 Vite

$ErrorActionPreference = "Stop"

# Nginx 配置文件路径（相对于 apps/frontend）
$nginxConf = "../../infra/nginx-dev.conf"

# 检查 Nginx 是否已在运行
$nginxRunning = Get-Process -Name "nginx" -ErrorAction SilentlyContinue
if ($nginxRunning) {
    Write-Host "[nginx] 已运行，跳过启动" -ForegroundColor Cyan
} else {
    Write-Host "[nginx] 启动中..." -ForegroundColor Green
    nginx -c $nginxConf
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Nginx 启动失败"
        exit 1
    }
    Start-Sleep -Milliseconds 500
}

# 启动 Vite
try {
    Write-Host "[vite] 启动中..." -ForegroundColor Green
    node scripts/free-dev-port.mjs
    & npx vite
} finally {
    # Vite 退出后自动停止 Nginx
    Write-Host "[nginx] 停止中..." -ForegroundColor Yellow
    Stop-Process -Name "nginx" -Force -ErrorAction SilentlyContinue
    Write-Host "[nginx] 已停止" -ForegroundColor Cyan
}
