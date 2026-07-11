#!/bin/bash

################################################################################
# ZentroApp - User Management System Deployment Script
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
#   ./deploy_user_management.sh <tenant_schema>
#   Example: ./deploy_user_management.sh ekk
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if schema is provided
if [ -z "$1" ]; then
    echo -e "${RED}❌ Error: Tenant schema not provided${NC}"
    echo "Usage: ./deploy_user_management.sh <tenant_schema>"
    echo "Example: ./deploy_user_management.sh ekk"
    exit 1
fi

SCHEMA=$1

echo ""
echo "================================================================================"
echo -e "${GREEN}ZentroApp - User Management System Deployment${NC}"
echo "================================================================================"
echo -e "${BLUE}Tenant Schema: ${SCHEMA}${NC}"
echo "================================================================================"
echo ""

# Function to run command with error handling
run_command() {
    local description=$1
    local command=$2
    
    echo -e "${YELLOW}▶ ${description}...${NC}"
    if eval $command; then
        echo -e "${GREEN}✅ ${description} - Success${NC}"
        echo ""
    else
        echo -e "${RED}❌ ${description} - Failed${NC}"
        exit 1
    fi
}

# Step 1: Run migrations
run_command "Running database migrations" \
    "python manage.py migrate_schemas"

# Step 2: Populate Page Objects
run_command "Populating page objects (including Purchase/Payment History & User Management)" \
    "python manage.py tenant_command populate_page_objects --schema=${SCHEMA}"

# Step 3: Setup Page Permissions
run_command "Setting up page permissions and permission sets" \
    "python manage.py tenant_command setup_page_permissions --schema=${SCHEMA}"

# Step 3b: Dimension Backfill (optional - for multi-branch)
echo -e "${YELLOW}▶ Run dimension backfill (--first-branch) for this tenant? (y/n)${NC}"
read -p "Choice: " run_backfill
if [ "$run_backfill" = "y" ] || [ "$run_backfill" = "Y" ]; then
    run_command "Backfilling entry dimensions with first branch" \
        "python manage.py tenant_command backfill_entry_dimensions --schema=${SCHEMA} --first-branch"
fi

# Step 4: Collect static files (if needed)
echo -e "${YELLOW}▶ Do you want to collect static files? (y/n)${NC}"
read -p "Choice: " collect_static
if [ "$collect_static" = "y" ] || [ "$collect_static" = "Y" ]; then
    run_command "Collecting static files" \
        "python manage.py collectstatic --noinput"
fi

echo ""
echo "================================================================================"
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE!${NC}"
echo "================================================================================"
echo ""
echo -e "${BLUE}📋 What was deployed:${NC}"
echo "  ✅ Database migrations applied"
echo "  ✅ Page objects created/updated:"
echo "     • User Management (ID: 10801)"
echo "     • User Group Management (ID: 10802)"
echo "     • Permission Set Management (ID: 10803)"
echo "     • User Roles Management (ID: 10804)"
echo "     • Role Center Management (ID: 10805)"
echo "     • Purchase History (ID: 10302)"
echo "     • Payment History (ID: 10402)"
echo "  ✅ Permission sets created/updated:"
echo "     • USER_MGMT_FULL - Full access to user management"
echo "     • USER_MGMT_BASIC - Basic user management access"
echo "     • USER_MGMT_VIEW_ONLY - View-only user management"
echo "     • PURCHASES_FULL - Now includes Purchase History"
echo "     • PAYMENTS_FULL - Now includes Payment History"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT POST-DEPLOYMENT STEPS:${NC}"
echo "  1. Log into Django Admin: http://your-domain/admin/"
echo "  2. Create or update Role Centers:"
echo "     - Admin Center should include 'user_management' module"
echo "  3. Assign permission sets to user groups:"
echo "     - Admin group should have USER_MGMT_FULL"
echo "     - Admin group should have PURCHASES_FULL and PAYMENTS_FULL"
echo "  4. Users must LOG OUT and LOG BACK IN to get updated JWT tokens"
echo "  5. Test the new features:"
echo "     - Navigate to User Management module"
echo "     - Check Purchase History and Payment History links"
echo ""
echo -e "${GREEN}🎉 Deployment successful!${NC}"
echo "================================================================================"
echo ""






