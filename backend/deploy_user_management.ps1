################################################################################
# ZentroApp - User Management System Deployment Script (PowerShell)
# 
# This script deploys the new User Management system to production
# 
# Features included:
# - User Management Module (Users, User Groups, Permission Sets, Roles, Role Centers)
# - Purchase History & Payment History pages
# - Auto-generated codes for User Groups and Role Centers
# - Complete permission system setup
#
# Usage:
#   .\deploy_user_management.ps1 -Schema <tenant_schema>
#   Example: .\deploy_user_management.ps1 -Schema ekk
################################################################################

param(
    [Parameter(Mandatory=$true)]
    [string]$Schema
)

# Function to write colored output
function Write-ColorOutput($ForegroundColor, $Message) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    Write-Output $Message
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Success($Message) {
    Write-ColorOutput Green "✅ $Message"
}

function Write-Info($Message) {
    Write-ColorOutput Cyan "ℹ️  $Message"
}

function Write-Warning($Message) {
    Write-ColorOutput Yellow "⚠️  $Message"
}

function Write-Error-Custom($Message) {
    Write-ColorOutput Red "❌ $Message"
}

function Write-Header($Message) {
    Write-Output ""
    Write-Output "================================================================================"
    Write-ColorOutput Green $Message
    Write-Output "================================================================================"
    Write-Output ""
}

# Function to run command with error handling
function Run-Command {
    param(
        [string]$Description,
        [scriptblock]$Command
    )
    
    Write-Info "$Description..."
    try {
        & $Command
        Write-Success "$Description - Complete"
        Write-Output ""
    }
    catch {
        Write-Error-Custom "$Description - Failed"
        Write-Error-Custom $_.Exception.Message
        exit 1
    }
}

# Main deployment
Write-Header "ZentroApp - User Management System Deployment"
Write-Info "Tenant Schema: $Schema"
Write-Output "================================================================================"
Write-Output ""

# Step 1: Activate virtual environment (if exists)
if (Test-Path ".\env\Scripts\Activate.ps1") {
    Write-Info "Activating virtual environment..."
    & .\env\Scripts\Activate.ps1
    Write-Success "Virtual environment activated"
    Write-Output ""
}

# Step 2: Run migrations
Run-Command -Description "Running database migrations" -Command {
    python manage.py migrate_schemas
}

# Step 3: Populate Page Objects
Run-Command -Description "Populating page objects (including Purchase/Payment History & User Management)" -Command {
    python manage.py tenant_command populate_page_objects --schema=$Schema
}

# Step 4: Setup Page Permissions
Run-Command -Description "Setting up page permissions and permission sets" -Command {
    python manage.py tenant_command setup_page_permissions --schema=$Schema
}

# Step 4b: Dimension Backfill (optional - for multi-branch)
$runBackfill = Read-Host "Run dimension backfill (--first-branch) for this tenant? (y/n)"
if ($runBackfill -eq "y" -or $runBackfill -eq "Y") {
    Run-Command -Description "Backfilling entry dimensions with first branch" -Command {
        python manage.py tenant_command backfill_entry_dimensions --schema=$Schema --first-branch
    }
}

# Step 5: Collect static files (optional)
$collectStatic = Read-Host "Do you want to collect static files? (y/n)"
if ($collectStatic -eq "y" -or $collectStatic -eq "Y") {
    Run-Command -Description "Collecting static files" -Command {
        python manage.py collectstatic --noinput
    }
}

# Deployment summary
Write-Header "✅ DEPLOYMENT COMPLETE!"

Write-ColorOutput Cyan "📋 What was deployed:"
Write-Output "  ✅ Database migrations applied"
Write-Output "  ✅ Page objects created/updated:"
Write-Output "     • User Management (ID: 10801)"
Write-Output "     • User Group Management (ID: 10802)"
Write-Output "     • Permission Set Management (ID: 10803)"
Write-Output "     • User Roles Management (ID: 10804)"
Write-Output "     • Role Center Management (ID: 10805)"
Write-Output "     • Purchase History (ID: 10302)"
Write-Output "     • Payment History (ID: 10402)"
Write-Output "  ✅ Permission sets created/updated:"
Write-Output "     • USER_MGMT_FULL - Full access to user management"
Write-Output "     • USER_MGMT_BASIC - Basic user management access"
Write-Output "     • USER_MGMT_VIEW_ONLY - View-only user management"
Write-Output "     • PURCHASES_FULL - Now includes Purchase History"
Write-Output "     • PAYMENTS_FULL - Now includes Payment History"
Write-Output ""
Write-Warning "IMPORTANT POST-DEPLOYMENT STEPS:"
Write-Output "  1. Log into Django Admin: http://your-domain/admin/"
Write-Output "  2. Create or update Role Centers:"
Write-Output "     - Admin Center should include 'user_management' module"
Write-Output "  3. Assign permission sets to user groups:"
Write-Output "     - Admin group should have USER_MGMT_FULL"
Write-Output "     - Admin group should have PURCHASES_FULL and PAYMENTS_FULL"
Write-Output "  4. Users must LOG OUT and LOG BACK IN to get updated JWT tokens"
Write-Output "  5. Test the new features:"
Write-Output "     - Navigate to User Management module"
Write-Output "     - Check Purchase History and Payment History links"
Write-Output ""
Write-Success "🎉 Deployment successful!"
Write-Output "================================================================================"
Write-Output ""






