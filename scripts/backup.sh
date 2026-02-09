#!/bin/bash

# Create backup directory with timestamp
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "💾 Backing up ronku_bot..."
echo "   Destination: $BACKUP_DIR"

# Backup database
echo "📦 Backing up database..."
if [ -f "data/sqlite/ronku-bot.db" ]; then
    cp data/sqlite/ronku-bot.db "$BACKUP_DIR/"
    echo "   ✅ Database backed up"
else
    echo "   ⚠️  No database file found"
fi

# Backup .env (without sensitive data)
echo "📝 Backing up configuration..."
cp .env "$BACKUP_DIR/"
echo "   ✅ Configuration backed up"

# Backup workflows
echo "📁 Backing up workflows..."
if [ -d "n8n-workflows" ] && [ "$(ls -A n8n-workflows)" ]; then
    cp -r n8n-workflows "$BACKUP_DIR/"
    echo "   ✅ Workflows backed up"
else
    echo "   ⚠️  No workflow files found"
fi

# Create backup info
echo "📋 Creating backup info..."
cat > "$BACKUP_DIR/BACKUP_INFO.txt" << EOF
ronku_bot Backup
================
Date: $(date)
Version: 1.0

Contents:
- ronku-bot.db: Conversation history and memory
- .env: Configuration (includes API keys)
- n8n-workflows/: Exported workflow files

To restore:
1. Copy .env back to project root
2. Copy ronku-bot.db to data/sqlite/
3. Copy workflows to n8n-workflows/
4. Import workflows in n8n UI
EOF

echo ""
echo "✅ Backup complete!"
echo "   Location: $BACKUP_DIR"
echo ""
echo "💡 To restore from this backup:"
echo "   cp $BACKUP_DIR/.env ."
echo "   cp $BACKUP_DIR/ronku-bot.db data/sqlite/"
echo "   cp -r $BACKUP_DIR/n8n-workflows/* n8n-workflows/"
