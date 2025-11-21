#!/usr/bin/env bash
# Generate test projects for various base images and validate them

set -euo pipefail

# List of test cases: "name|template"
TEST_CASES=(
	"python|python"
	"python-3-11|python:3.11"
	"ubuntu|ubuntu"
	"ubuntu-22-04|ubuntu:22.04"
	"debian|debian"
	"alpine|alpine"
	"pytorch|pytorch/pytorch"
	"pytorch-cuda|pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime"
	"nvidia-cuda|nvidia/cuda:12.4.0-runtime-ubuntu22.04"
)

# Output directory
OUTPUT_DIR="test-generated-projects"

# Clean previous run
if [ -d "$OUTPUT_DIR" ]; then
	echo "Cleaning previous test projects..."
	rm -rf "$OUTPUT_DIR"
fi

mkdir -p "$OUTPUT_DIR"

echo "=== Generating Test Projects ==="
echo ""

# Track results
TOTAL=0
PASSED=0
FAILED=0

for test_case in "${TEST_CASES[@]}"; do
	IFS='|' read -r name template <<<"$test_case"
	TOTAL=$((TOTAL + 1))

	echo "[$TOTAL/${#TEST_CASES[@]}] Generating $name (template: $template)..."

	PROJECT_DIR="$OUTPUT_DIR/$name"

	# Create project directory
	mkdir -p "$PROJECT_DIR"
	cd "$PROJECT_DIR"

	# Initialize
	if ! cm init --here "$template" >/dev/null 2>&1; then
		echo "  ✗ Failed to initialize"
		FAILED=$((FAILED + 1))
		cd - >/dev/null
		continue
	fi

	# Validate generated files exist
	MISSING=0
	for file in "Dockerfile" "Justfile" "container-magic.yaml" "build.sh" "run.sh" ".gitignore"; do
		if [ ! -f "$file" ]; then
			echo "  ✗ Missing: $file"
			MISSING=$((MISSING + 1))
		fi
	done

	if [ $MISSING -gt 0 ]; then
		echo "  ✗ Missing $MISSING files"
		FAILED=$((FAILED + 1))
		cd - >/dev/null
		continue
	fi

	# Validate YAML is readable
	if ! cm update >/dev/null 2>&1; then
		echo "  ✗ Config validation failed"
		FAILED=$((FAILED + 1))
		cd - >/dev/null
		continue
	fi

	# Check Dockerfile syntax (basic check)
	if ! grep -q "^FROM.*AS base" Dockerfile; then
		echo "  ✗ Dockerfile missing base stage"
		FAILED=$((FAILED + 1))
		cd - >/dev/null
		continue
	fi

	# Check Justfile syntax (basic check)
	if ! grep -q "^build.*:" Justfile; then
		echo "  ✗ Justfile missing build target"
		FAILED=$((FAILED + 1))
		cd - >/dev/null
		continue
	fi

	echo "  ✓ All checks passed"
	PASSED=$((PASSED + 1))

	cd - >/dev/null
done

echo ""
echo "=== Summary ==="
echo "Total:  $TOTAL"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""
echo "Generated projects in: $OUTPUT_DIR/"

if [ $FAILED -gt 0 ]; then
	exit 1
fi
