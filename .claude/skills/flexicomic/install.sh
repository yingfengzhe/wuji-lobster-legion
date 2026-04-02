#!/usr/bin/env bash

# flexicomic installation script

set -e

echo "🎨 flexicomic Installation"
echo "=========================="
echo ""

# Check if running from the correct directory
if [ ! -f ".claude-plugin/marketplace.json" ]; then
    echo "❌ Error: Please run this script from the flexicomic directory"
    echo "   cd flexicomic && ./install.sh"
    exit 1
fi

# Detect Claude plugins directory
CLAUDE_DIR="$HOME/.claude-plugins"
if [ -d "$CLAUDE_DIR" ]; then
    echo "✓ Found Claude plugins directory: $CLAUDE_DIR"
else
    echo "⚠ Claude plugins directory not found. You may need to create it manually."
    CLAUDE_DIR="$HOME/.claude-plugins"
    mkdir -p "$CLAUDE_DIR"
    echo "✓ Created: $CLAUDE_DIR"
fi

# Ask for installation method
echo ""
echo "Choose installation method:"
echo "  1) Install to ~/.claude-plugins (recommended)"
echo "  2) Install to current directory"
echo "  3) Create symlink to current directory"
read -p "Select [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "Installing to Claude plugins directory..."
        CURRENT_DIR=$(pwd)
        ln -sf "$CURRENT_DIR" "$CLAUDE_DIR/flexicomic"
        echo "✓ Created symlink: $CLAUDE_DIR/flexicomic -> $CURRENT_DIR"
        ;;
    2)
        echo ""
        echo "Installing to current directory..."
        echo "✓ Ready to use from: $(pwd)"
        ;;
    3)
        echo ""
        echo "Creating symlink..."
        CURRENT_DIR=$(pwd)
        ln -sf "$CURRENT_DIR" "$CLAUDE_DIR/flexicomic"
        echo "✓ Created symlink: $CLAUDE_DIR/flexicomic -> $CURRENT_DIR"
        ;;
    *)
        echo "Invalid choice. Installation cancelled."
        exit 1
        ;;
esac

# Check for Bun
echo ""
if command -v bun &> /dev/null; then
    echo "✓ Bun is installed: $(bun --version)"
else
    echo "⚠ Bun not found. Install from https://bun.sh/"
    echo "  curl -fsSL https://bun.sh/install | bash"
fi

# Create .env directory
ENV_DIR="$HOME/.flexicomic"
if [ ! -d "$ENV_DIR" ]; then
    mkdir -p "$ENV_DIR"
    echo "✓ Created config directory: $ENV_DIR"
fi

# Check for existing .env
if [ ! -f "$ENV_DIR/.env" ]; then
    echo ""
    echo "⚠ No API key found. Configure your image generation API:"
    echo ""
    echo "  Create $ENV_DIR/.env with:"
    echo "    GOOGLE_API_KEY=your_key"
    echo "  Or:"
    echo "    OPENAI_API_KEY=your_key"
    echo "  Or:"
    echo "    DASHSCOPE_API_KEY=your_key"
else
    echo "✓ API config exists: $ENV_DIR/.env"
fi

echo ""
echo "=========================="
echo "✅ Installation complete!"
echo ""
echo "Usage:"
if [ "$choice" = "1" ] || [ "$choice" = "3" ]; then
    echo "  In Claude Code, just ask to create a comic!"
else
    echo "  cd $(pwd)"
    echo "  bun scripts/main.ts init my-comic"
fi
echo ""
echo "For help:"
echo "  bun scripts/main.ts --help"
echo ""
