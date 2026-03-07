# Quick Setup Script for Image Service
# Run this in PowerShell with your virtual environment activated

$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param([string]$StepName)
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $StepName (exit code $LASTEXITCODE)"
    }
}

Write-Host ("=" * 72) -ForegroundColor Cyan
Write-Host " Image Service - Quick Setup" -ForegroundColor Green
Write-Host ("=" * 72) -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if venv is activated
Write-Host "[1/6] Checking virtual environment..." -ForegroundColor Yellow

if ($env:VIRTUAL_ENV) {
    Write-Host "OK Virtual environment is activated: $env:VIRTUAL_ENV" -ForegroundColor Green
}
else {
    Write-Host "ERROR Virtual environment not activated!" -ForegroundColor Red
    Write-Host "Please run: .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Optional cleanup: remove broken package artifacts that trigger '~ympy' warnings
$sitePackages = python -c "import site; print(site.getsitepackages()[0])"
if ($LASTEXITCODE -eq 0 -and (Test-Path $sitePackages)) {
    Get-ChildItem -Path $sitePackages -Filter "~ympy*" -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# Step 2: Upgrade pip
Write-Host "[2/6] Upgrading pip..." -ForegroundColor Yellow

python -m pip install --upgrade pip
Assert-LastExitCode "Upgrade pip"

Write-Host "OK pip upgraded" -ForegroundColor Green
Write-Host ""

# Step 3: Install PyTorch
Write-Host "[3/6] Installing PyTorch with CUDA 12.1 support..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..." -ForegroundColor Gray

# Remove any existing CPU torch stack first
pip uninstall -y torch torchvision torchaudio
Assert-LastExitCode "Uninstall existing torch stack"

# cu121 index currently provides up to 2.5.1+cu121
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
Assert-LastExitCode "Install CUDA torch stack"

Write-Host "OK PyTorch installed" -ForegroundColor Green
Write-Host ""

# Step 4: Verify CUDA
Write-Host "[4/6] Verifying CUDA availability..." -ForegroundColor Yellow

$cudaCheck = python -c 'import torch; print(torch.cuda.is_available())'
$cudaCheck = $cudaCheck.Trim()

if ($cudaCheck -eq "True") {
    
    $gpuName = python -c 'import torch; print(torch.cuda.get_device_name(0))'
    $gpuName = $gpuName.Trim()

    Write-Host "OK CUDA is available! GPU: $gpuName" -ForegroundColor Green
}
else {
    Write-Host "WARNING CUDA not available. Service will run on CPU." -ForegroundColor Yellow
}

Write-Host ""

# Step 5: Install dependencies
Write-Host "[5/6] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..." -ForegroundColor Gray

pip install -r requirements.txt
Assert-LastExitCode "Install requirements"

# Re-assert CUDA torch stack in case other installs touched torch packages
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
Assert-LastExitCode "Re-assert CUDA torch stack"

Write-Host "OK Dependencies installed" -ForegroundColor Green
Write-Host ""

# Step 6: Verify installation
Write-Host "[6/6] Verifying installation..." -ForegroundColor Yellow

$versions = python -c "import torch, transformers, pymongo, fastapi; print('torch:', torch.__version__); print('transformers:', transformers.__version__); print('pymongo:', pymongo.__version__); print('fastapi:', fastapi.__version__)"
Assert-LastExitCode "Verify installation"

Write-Host $versions -ForegroundColor Gray
Write-Host "OK Installation verified" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host ("=" * 72) -ForegroundColor Cyan
Write-Host " Setup Complete!" -ForegroundColor Green
Write-Host ("=" * 72) -ForegroundColor Cyan
Write-Host ""

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Place images in: data\post_images\" -ForegroundColor White
Write-Host "2. Start service: uvicorn api.main:app --host 0.0.0.0 --port 8002" -ForegroundColor White
Write-Host "3. Run analysis: Invoke-RestMethod -Uri 'http://localhost:8002/run' -Method POST" -ForegroundColor White
Write-Host "4. Check results in MongoDB (dellinnovate.image_analysis_results)" -ForegroundColor White
Write-Host ""
Write-Host "For detailed documentation, see SETUP_GUIDE.md" -ForegroundColor Gray
Write-Host ""