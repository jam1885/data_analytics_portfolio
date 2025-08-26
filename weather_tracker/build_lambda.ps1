# build_lambda.ps1
# PowerShell script to automate Lambda packaging

# Set variables
$lambdaFolder = "lambda_code"
$zipFile = "lambda_package.zip"
$sourceFile = "lambda_function.py"

# Remove old folder if it exists
if (Test-Path $lambdaFolder) {
    Remove-Item -Recurse -Force $lambdaFolder
}

# Create folder
New-Item -ItemType Directory -Path $lambdaFolder

# Copy source code
Copy-Item $sourceFile $lambdaFolder\

# Install dependencies into folder
pip install requests -t $lambdaFolder\

# Remove old zip if exists
if (Test-Path $zipFile) {
    Remove-Item $zipFile
}

# Compress folder into zip
Compress-Archive -Path $lambdaFolder\* -DestinationPath $zipFile -Force

Write-Output "Lambda package created: $zipFile"
