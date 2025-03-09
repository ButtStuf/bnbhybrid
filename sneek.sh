#!/bin/bash
set -e  # Exit on any error

echo "🚀 Starting Flap Arbitrage Deployment..."

# ✅ Install required dependencies
echo "📦 Installing Node.js and Python dependencies..."
npm install --save-dev hardhat @openzeppelin/contracts @nomicfoundation/hardhat-toolbox
pip3 install -q web3 flask requests python-dotenv

# ✅ Compile the Solidity contract
echo "🔨 Compiling Flap.sol..."
npx hardhat compile

# ✅ Deploy the contract to Binance Smart Chain (BSC)
echo "🚀 Deploying Flap smart contract..."
DEPLOY_OUTPUT=$(npx hardhat run scripts/deploy.js --network bsc)

# ✅ Extract deployed contract address
FLAP_CONTRACT_ADDRESS=$(echo "$DEPLOY_OUTPUT" | grep "Contract deployed to:" | awk '{print $4}')
echo "✅ Flap Contract deployed at: $FLAP_CONTRACT_ADDRESS"

# ✅ Update `.env` file with correct addresses
echo "🔧 Updating environment variables..."
cat <<EOF > .env
BSC_RPC_URL=https://bsc-dataseed.binance.org/
PRIVATE_KEY=your_private_key_here
BOT_WALLET_ADDRESS=your_wallet_address_here
FLAP_CONTRACT_ADDRESS=$FLAP_CONTRACT_ADDRESS
ALCHEMY_API_URL=https://bnb-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_API_KEY
EOF
echo "✅ Environment variables updated!"

# ✅ Extract contract ABI for Python bot
echo "📜 Extracting contract ABI..."
ABI_PATH="artifacts/contracts/Flap.sol/Flap.json"
jq '.abi' $ABI_PATH > flap_abi.json
echo "✅ ABI saved to flap_abi.json"

# ✅ Start the Python arbitrage bot
echo "🚀 Starting the arbitrage bot..."
nohup python3 snakeflap.py > logs/arbitrage.log 2>&1 &

echo "✅ Arbitrage bot is running in the background!"
echo "📊 Monitor bot status at: http://localhost 6540/status"
