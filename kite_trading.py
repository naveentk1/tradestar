import logging
from kiteconnect import KiteConnect

logging.basicConfig(level=logging.INFO)

API_KEY = "q0ia8ex81o40fdfx"

# Read the saved access token
with open('access_token.txt', 'r') as f:
    access_token = f.read().strip()

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(access_token)

# Test connection
try:
    profile = kite.profile()
    logging.info(f"✅ Logged in as: {profile['user_name']}")
    logging.info(f"Email: {profile['email']}")

    margins = kite.margins()
    available = margins['equity']['available']['live_balance']
    logging.info(f"💰 Available balance: ₹{available:.2f}")

except Exception as e:
    logging.error(f"❌ Connection failed: {e}")
    exit(1)

# Place an order (EXAMPLE - be careful!)
try:
    order_id = kite.place_order(
        tradingsymbol="INFY",
        exchange=kite.EXCHANGE_NSE,
        transaction_type=kite.TRANSACTION_TYPE_BUY,
        quantity=1,
        order_type=kite.ORDER_TYPE_MARKET,
        product=kite.PRODUCT_MIS,  # MIS = intraday, CNC = delivery
        variety=kite.VARIETY_REGULAR  # Not AMO unless you want after-market order
    )
    logging.info(f"✅ Order placed. ID: {order_id}")

except Exception as e:
    logging.error(f"❌ Order failed: {e}")

# Fetch all orders
orders = kite.orders()
logging.info(f"Total orders today: {len(orders)}")

# Get your positions
positions = kite.positions()
logging.info(f"Open positions: {positions['net']}")

# Get instrument list (takes a few seconds)
instruments = kite.instruments("NSE")
logging.info(f"Total NSE instruments: {len(instruments)}")