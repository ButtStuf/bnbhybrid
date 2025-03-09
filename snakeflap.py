import time
import json
import requests
import os
from web3 import Web3
from dotenv import load_dotenv
from flask import Flask, jsonify

# Load environment variables
load_dotenv()
BSC_RPC_URL = os.getenv("BSC_RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
BOT_WALLET_ADDRESS = os.getenv("BOT_WALLET_ADDRESS")
FLAP_CONTRACT_ADDRESS = os.getenv("FLAP_CONTRACT_ADDRESS")
ALCHEMY_API_URL = os.getenv("ALCHEMY_API_URL")

# Connect to Binance Smart Chain
web3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
assert web3.is_connected(), "❌ Web3 connection failed!"

# Load contract ABI
with open("flap_abi.json", "r") as f:
    contract_abi = json.load(f)

# Initialize contract
flap_contract = web3.eth.contract(address=Web3.to_checksum_address(FLAP_CONTRACT_ADDRESS), abi=contract_abi)

# Supported tokens for arbitrage
TOKENS = {
    "BUSD": "0xe9e7cea3dedca5984780bafc599bd69add087d56",
    "USDT": "0x55d398326f99059ff775485246999027b3197955"
}

# API endpoints for live price feeds
DEX_API = "https://api.pancakeswap.info/api/v2/tokens/"

# Flask app for monitoring
app = Flask(__name__)
bot_status = {"last_profit": 0, "last_tx": None}

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify(bot_status)

# Function to fetch token price from PancakeSwap
def get_token_price(token_address):
    try:
        response = requests.get(f"{DEX_API}{token_address}", timeout=5).json()
        return float(response["data"]["price"])
    except Exception as e:
        print(f"❌ Error fetching price: {e}")
        return None

# Function to check wallet balance before executing trades
def check_gas_balance():
    balance = web3.eth.get_balance(BOT_WALLET_ADDRESS)
    return web3.from_wei(balance, "ether") > 0.02  # Ensure at least 0.02 BNB for gas fees

# Function to simulate transaction before execution
def simulate_transaction(token, amount):
    data = {
        "jsonrpc": "2.0",
        "method": "alchemy_simulateAssetChanges",
        "id": 1,
        "params": [
            {
                "from": BOT_WALLET_ADDRESS,
                "to": token,
                "value": hex(amount)
            }
        ]
    }

    try:
        response = requests.post(ALCHEMY_API_URL, json=data, headers={"Content-Type": "application/json"})
        result = response.json()
        return "error" not in result  # Returns True if simulation is successful
    except Exception as e:
        print(f"❌ Simulation failed: {e}")
        return False

# Function to execute flash loan if conditions are met
def execute_flash_loan(token, amount):
    if not check_gas_balance():
        print("⚠️ Insufficient BNB for gas fees!")
        return

    if not simulate_transaction(token, amount):
        print("⚠️ Simulation failed! Skipping transaction.")
        return

    try:
        tx = flap_contract.functions.executeFlashLoan(token, amount).build_transaction({
            "from": BOT_WALLET_ADDRESS,
            "gas": 3000000,
            "gasPrice": web3.to_wei("5", "gwei"),
            "nonce": web3.eth.get_transaction_count(BOT_WALLET_ADDRESS)
        })

        signed_tx = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        bot_status["last_tx"] = tx_hash.hex()
        print(f"✅ Flash loan executed! TX: {tx_hash.hex()}")
    except Exception as e:
        print(f"❌ Flash loan execution failed: {e}")

# Function to search for profitable arbitrage opportunities
def find_profitable_arbitrage():
    for token_name, token_address in TOKENS.items():
        estimated_profit = flap_contract.functions.performArbitrage(token_address, 1 * 10**18).call()
        token_price = get_token_price(token_address)

        if token_price is None:
            continue

        estimated_profit_usd = (estimated_profit / 10**18) * token_price
        print(f"[🔍] {token_name} Estimated Profit: ${estimated_profit_usd:.2f}")

        if 5 <= estimated_profit_usd <= 100:
            execute_flash_loan(token_address, 1 * 10**18)

# Main bot loop (executes every 5 seconds)
def main():
    while True:
        try:
            print("\n[🔍] Searching for arbitrage opportunities...")
            find_profitable_arbitrage()
        except Exception as e:
            print(f"❌ Error: {e}")

        time.sleep(5)  # Run every 5 seconds

# Start the bot and Flask monitoring
if __name__ == "__main__":
    from threading import Thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=5000)).start()
    main()
