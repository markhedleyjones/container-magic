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

# Check for linting tools
YAMLLINT=$(command -v yamllint || echo "")
HADOLINT=$(command -v hadolint || echo "")
SHELLCHECK=$(command -v shellcheck || echo "")
JUST=$(command -v just || echo "")

# Validate a file with appropriate linter
validate_file() {
	local file=$1
	local errors=0

	case "$file" in
	*.yaml)
		if [ -n "$YAMLLINT" ]; then
			if ! yamllint -d relaxed "$file" >/dev/null 2>&1; then
				echo "    ✗ YAML lint failed: $file"
				errors=$((errors + 1))
			fi
		fi
		;;
	Dockerfile)
		if [ -n "$HADOLINT" ]; then
			# Only fail on errors, not warnings (--failure-threshold error)
			if ! hadolint --failure-threshold error "$file" >/dev/null 2>&1; then
				echo "    ✗ Dockerfile lint failed"
				errors=$((errors + 1))
			fi
		fi
		;;
	*.sh)
		if [ -n "$SHELLCHECK" ]; then
			if ! shellcheck "$file" >/dev/null 2>&1; then
				echo "    ✗ Shell lint failed: $file"
				errors=$((errors + 1))
			fi
		fi
		;;
	Justfile)
		if [ -n "$JUST" ]; then
			if ! just --justfile "$file" --summary >/dev/null 2>&1; then
				echo "    ✗ Justfile syntax failed"
				errors=$((errors + 1))
			fi
		fi
		;;
	esac

	return $errors
}

# Clean previous run
if [ -d "$OUTPUT_DIR" ]; then
	echo "Cleaning previous test projects..."
	rm -rf "$OUTPUT_DIR"
fi

mkdir -p "$OUTPUT_DIR"

echo "=== Generating Test Projects ==="
echo ""
echo "Available linters:"
[ -n "$YAMLLINT" ] && echo "  ✓ yamllint" || echo "  ✗ yamllint (install with: pip install yamllint)"
[ -n "$HADOLINT" ] && echo "  ✓ hadolint" || echo "  ✗ hadolint (install from: https://github.com/hadolint/hadolint)"
[ -n "$SHELLCHECK" ] && echo "  ✓ shellcheck" || echo "  ✗ shellcheck (install with: dnf install shellcheck)"
[ -n "$JUST" ] && echo "  ✓ just" || echo "  ✗ just (install from: https://github.com/casey/just)"
echo ""

# Track results
TOTAL=0
PASSED=0
FAILED=0

for test_case in "${TEST_CASES[@]}"; do
	IFS='|' read -r name template <<<"$test_case"

	# Test both compact and full variants
	for variant in "full" "compact"; do
		TOTAL=$((TOTAL + 1))

		if [ "$variant" = "compact" ]; then
			variant_name="${name}-compact"
			compact_flag="--compact"
			config_file="cm.yaml"
		else
			variant_name="${name}"
			compact_flag=""
			config_file="container-magic.yaml"
		fi

		echo "[$TOTAL/$((${#TEST_CASES[@]} * 2))] Generating $variant_name (template: $template)..."

		PROJECT_DIR="$OUTPUT_DIR/$variant_name"

		# Create project directory
		mkdir -p "$PROJECT_DIR"
		cd "$PROJECT_DIR"

		# Initialize
		if ! cm init --here $compact_flag "$template" >/dev/null 2>&1; then
			echo "  ✗ Failed to initialize"
			FAILED=$((FAILED + 1))
			cd - >/dev/null
			continue
		fi

		# Validate generated files exist
		MISSING=0
		lint_errors=0
		for file in "Dockerfile" "Justfile" "$config_file" "build.sh" "run.sh" ".gitignore"; do
			if [ ! -f "$file" ]; then
				echo "  ✗ Missing: $file"
				MISSING=$((MISSING + 1))
			else
				# Validate file with linter
				if ! validate_file "$file"; then
					lint_errors=$((lint_errors + 1))
				fi
			fi
		done

		if [ $MISSING -gt 0 ]; then
			echo "  ✗ Missing $MISSING files"
			FAILED=$((FAILED + 1))
			cd - >/dev/null
			continue
		fi

		if [ $lint_errors -gt 0 ]; then
			echo "  ✗ $lint_errors linting errors"
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

		# Check for 'from:' not 'frm:' in YAML
		if grep -q "frm:" "$config_file"; then
			echo "  ✗ Config uses 'frm:' instead of 'from:'"
			FAILED=$((FAILED + 1))
			cd - >/dev/null
			continue
		fi

		# Compact should have no comments, full should have comments
		if [ "$variant" = "compact" ]; then
			if grep -q "^#" "$config_file"; then
				echo "  ✗ Compact config contains comments"
				FAILED=$((FAILED + 1))
				cd - >/dev/null
				continue
			fi
		else
			if ! grep -q "^# Project configuration" "$config_file"; then
				echo "  ✗ Full config missing comments"
				FAILED=$((FAILED + 1))
				cd - >/dev/null
				continue
			fi
		fi

		echo "  ✓ All checks passed"
		PASSED=$((PASSED + 1))

		cd - >/dev/null
	done
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
