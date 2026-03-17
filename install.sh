#!/usr/bin/env bash
set -euo pipefail

# Install pr-review-pack skill from the monorepo to ~/.claude/skills/pr-review-pack.
# For monorepo developers only. End users: git clone the downstream repo directly:
#   git clone https://github.com/joeyfezster/pr-review-pack.git ~/.claude/skills/pr-review-pack

INSTALL_DIR="$HOME/.claude/skills/pr-review-pack"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing pr-review-pack skill..."
echo "  Source: $SOURCE_DIR"
echo "  Target: $INSTALL_DIR"

# Clean previous installation
if [ -L "$INSTALL_DIR" ]; then
    echo "  Removing old symlink..."
    rm "$INSTALL_DIR"
elif [ -d "$INSTALL_DIR" ]; then
    echo "  Removing old installation..."
    rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR"

# Copy core files
cp "$SOURCE_DIR/SKILL.md" "$INSTALL_DIR/"
cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/package.json" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/package-lock.json" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/playwright.config.ts" "$INSTALL_DIR/" 2>/dev/null || true

# Copy directories (resolve symlinks with -L)
cp -RL "$SOURCE_DIR/scripts" "$INSTALL_DIR/scripts"
cp -RL "$SOURCE_DIR/review-prompts" "$INSTALL_DIR/review-prompts"
cp -RL "$SOURCE_DIR/references" "$INSTALL_DIR/references"
cp -RL "$SOURCE_DIR/assets" "$INSTALL_DIR/assets"
cp -RL "$SOURCE_DIR/e2e" "$INSTALL_DIR/e2e"
[ -d "$SOURCE_DIR/agents" ] && cp -RL "$SOURCE_DIR/agents" "$INSTALL_DIR/agents"

# Verify installation
VERIFY_FILES=(
    "SKILL.md"
    "scripts/review_pack_setup.py"
    "scripts/assemble_review_pack.py"
    "scripts/render_review_pack.py"
    "scripts/models.py"
    "scripts/run_deterministic_review.py"
    "review-prompts/code_health_review.md"
    "review-prompts/security_review.md"
    "review-prompts/test_integrity_review.md"
    "review-prompts/adversarial_review.md"
    "review-prompts/architecture_review.md"
    "review-prompts/synthesis_review.md"
    "references/schemas/ReviewConcept.schema.json"
    "assets/template_v2.html"
)

MISSING=0
for f in "${VERIFY_FILES[@]}"; do
    if [ ! -f "$INSTALL_DIR/$f" ]; then
        echo "  MISSING: $f"
        MISSING=$((MISSING + 1))
    fi
done

if [ "$MISSING" -gt 0 ]; then
    echo "ERROR: $MISSING files missing from installation."
    exit 1
fi

echo ""
echo "Installed successfully. ${#VERIFY_FILES[@]} critical files verified."
echo "Skill available at: $INSTALL_DIR"
