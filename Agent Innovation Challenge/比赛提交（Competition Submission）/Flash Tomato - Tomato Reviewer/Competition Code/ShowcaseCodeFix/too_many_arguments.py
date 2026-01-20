def create_user_profile(name, age, email, phone, address, city, state, zipcode, country, occupation, salary, department, manager, start_date, status):
    profile = {
        "name": name,
        "age": age,
        "email": email,
        "phone": phone,
        "address": address,
        "city": city,
        "state": state,
        "zipcode": zipcode,
        "country": country,
        "occupation": occupation,
        "salary": salary,
        "department": department,
        "manager": manager,
        "start_date": start_date,
        "status": status
    }
    return profile

def process_order(customer_id, product_id, quantity, price, discount, tax, shipping, payment_method, billing_address, shipping_address, order_date, delivery_date, notes):
    total = (quantity * price) - discount + tax + shipping
    return {
        "customer_id": customer_id,
        "product_id": product_id,
        "total": total,
        "payment_method": payment_method
    }

def main():
    profile = create_user_profile("John", 30, "john@example.com", "123-456-7890", "123 Main St", "New York", "NY", "10001", "USA", "Engineer", 100000, "IT", "Jane", "2024-01-01", "active")
    print(profile)

if __name__ == "__main__":
    main()
