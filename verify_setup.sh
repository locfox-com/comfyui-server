#!/bin/bash

# Final Verification Script for ComfyUI AI Image Server
# This script verifies all components are in place

echo "================================================"
echo "ComfyUI AI Image Server - Final Verification"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_passed=0
check_failed=0

check_item() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
        ((check_passed++))
    else
        echo -e "${RED}✗${NC} $2"
        ((check_failed++))
    fi
}

echo "Phase 4: ComfyUI Backend"
echo "-------------------------"

[ -f "worker/workflows/face_swap.json" ]
check_item $? "Face swap workflow template exists"

[ -f "worker/workflows/upscale.json" ]
check_item $? "Upscale workflow template exists"

[ -f "worker/workflows/remove_background.json" ]
check_item $? "Remove background workflow template exists"

[ -x "comfyui/download_models.sh" ]
check_item $? "Model download script exists and is executable"

echo ""
echo "Phase 5: Nginx Configuration"
echo "----------------------------"

[ -f "nginx/default.conf" ]
check_item $? "Nginx configuration exists"

grep -q "limit_req_zone" nginx/default.conf
check_item $? "Nginx has rate limiting configured"

grep -q "location /api/" nginx/default.conf
check_item $? "Nginx has API route configured"

grep -q "location /ws/" nginx/default.conf
check_item $? "Nginx has WebSocket route configured"

echo ""
echo "Phase 6: Integration Tests and Documentation"
echo "---------------------------------------------"

[ -f "tests/integration/test_full_flow.py" ]
check_item $? "Integration tests exist"

[ -f "tests/requirements.txt" ]
check_item $? "Test requirements file exists"

[ -f "docs/DEPLOYMENT.md" ]
check_item $? "Deployment documentation exists"

[ -f "docs/API.md" ]
check_item $? "API documentation exists"

[ -f "README.md" ]
check_item $? "Project README exists"

[ -f ".gitignore" ]
check_item $? "Git ignore file exists"

echo ""
echo "System Structure Verification"
echo "-------------------------------"

[ -d "api" ]
check_item $? "API directory exists"

[ -d "worker" ]
check_item $? "Worker directory exists"

[ -d "worker/processors" ]
check_item $? "Worker processors directory exists"

[ -d "worker/utils" ]
check_item $? "Worker utilities directory exists"

[ -d "comfyui" ]
check_item $? "ComfyUI directory exists"

[ -d "nginx" ]
check_item $? "Nginx directory exists"

[ -f "docker-compose.yml" ]
check_item $? "Docker Compose configuration exists"

[ -f ".env.example" ]
check_item $? "Environment example file exists"

echo ""
echo "JSON Validation"
echo "---------------"

python3 -m json.tool worker/workflows/face_swap.json > /dev/null 2>&1
check_item $? "face_swap.json is valid JSON"

python3 -m json.tool worker/workflows/upscale.json > /dev/null 2>&1
check_item $? "upscale.json is valid JSON"

python3 -m json.tool worker/workflows/remove_background.json > /dev/null 2>&1
check_item $? "remove_background.json is valid JSON"

echo ""
echo "================================================"
echo "Verification Complete"
echo "================================================"
echo -e "Passed: ${GREEN}${check_passed}${NC}"
echo -e "Failed: ${RED}${check_failed}${NC}"
echo ""

if [ $check_failed -eq 0 ]; then
    echo -e "${GREEN}All checks passed! The system is ready for deployment.${NC}"
    exit 0
else
    echo -e "${RED}Some checks failed. Please review the output above.${NC}"
    exit 1
fi
