import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_user_data(user_id, user_name, email):
    logger.info(f"Processing user data for user_id: {user_id}, name: {user_name}, email: {email}")
    result = {"id": user_id, "name": user_name, "email": email}
    logger.info(f"User data processed successfully: {result}")
    return result

def calculate_total(items):
    total = sum(item["price"] * item["quantity"] for item in items)
    logger.info(f"Calculated total for {len(items)} items: {total}")
    logger.debug(f"Detailed breakdown: {items}")
    return total

def handle_error(error_code, error_message, stack_trace):
    logger.error(f"Error occurred - code: {error_code}, message: {error_message}, trace: {stack_trace}")
    logger.warning(f"Error handling completed for code: {error_code}")

def process_transaction(transaction_id, amount, currency, timestamp):
    logger.info(f"Processing transaction {transaction_id} with amount {amount} {currency} at {timestamp}")
    if amount > 1000:
        logger.warning(f"Large transaction detected: {transaction_id} with amount {amount} {currency}")
    logger.info(f"Transaction {transaction_id} completed successfully")

def main():
    user_data = process_user_data(123, "John Doe", "john@example.com")
    print(user_data)
    
    items = [{"price": 10, "quantity": 2}, {"price": 5, "quantity": 3}]
    total = calculate_total(items)
    print(f"Total: {total}")
    
    handle_error(500, "Internal server error", "Traceback...")
    
    process_transaction("TXN-001", 1500, "USD", "2024-01-01 12:00:00")

if __name__ == "__main__":
    main()
