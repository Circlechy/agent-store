def calculate_sum(a, b):
    result = a + b

def get_user_name(user_id):
    if user_id == 1:
        return "John"
    elif user_id == 2:
        return "Jane"
    else:
        pass

def process_data(data):
    if data:
        processed = data * 2
        return processed

def validate_email(email):
    if "@" in email:
        if "." in email.split("@")[1]:
            return True
    else:
        return False

def main():
    result = calculate_sum(5, 3)
    print(result)
    
    name = get_user_name(3)
    print(name)
    
    processed = process_data(None)
    print(processed)

if __name__ == "__main__":
    main()
