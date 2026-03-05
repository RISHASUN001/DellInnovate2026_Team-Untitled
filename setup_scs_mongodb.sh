#!/bin/bash

echo "🚀 Setting up MongoDB for SCS Youth Helper Dashboard..."

# Install required Python packages
pip install pymongo python-dotenv

# Run setup
echo "📦 Creating collections and indexes..."
python database_setup/scs_mongodb_setup.py

# Run seed data
echo "🌱 Seeding data..."
python database_setup/scs_seed.py

echo "✅ Setup complete!"