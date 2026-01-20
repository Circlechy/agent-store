def complex_calculation(input_data):
    step1 = input_data * 2
    step2 = step1 + 10
    step3 = step2 - 5
    step4 = step3 * 3
    step5 = step4 / 2
    step6 = step5 + 7
    step7 = step6 - 3
    step8 = step7 * 4
    step9 = step8 / 2
    step10 = step9 + 1
    step11 = step10 - 2
    step12 = step11 * 3
    step13 = step12 / 4
    step14 = step13 + 5
    step15 = step14 - 1
    step16 = step15 * 2
    step17 = step16 / 3
    step18 = step17 + 4
    step19 = step18 - 2
    step20 = step19 * 5
    return step20

def process_user_info(name, age, email, phone):
    name_upper = name.upper()
    age_squared = age * age
    email_domain = email.split("@")[1]
    phone_formatted = phone.replace("-", "")
    name_length = len(name)
    age_doubled = age * 2
    email_length = len(email)
    phone_length = len(phone)
    name_reversed = name[::-1]
    age_modulo = age % 10
    email_upper = email.upper()
    phone_reversed = phone[::-1]
    return {
        "name": name_upper,
        "age": age_squared,
        "email": email_domain,
        "phone": phone_formatted
    }

def main():
    result = complex_calculation(10)
    print(result)
    
    info = process_user_info("John", 30, "john@example.com", "123-456-7890")
    print(info)

if __name__ == "__main__":
    main()
