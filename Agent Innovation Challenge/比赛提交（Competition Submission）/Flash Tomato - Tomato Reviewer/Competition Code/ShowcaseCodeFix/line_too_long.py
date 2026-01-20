def process_user_data(user_name, user_email, user_phone, user_address, user_city, user_state, user_zipcode, user_country, user_occupation):
    user_profile = {"name": user_name, "email": user_email, "phone": user_phone, "address": user_address, "city": user_city, "state": user_state, "zipcode": user_zipcode, "country": user_country, "occupation": user_occupation}
    return user_profile

def calculate_complex_formula(a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t):
    result = a * b + c * d - e * f + g * h / i * j - k * l + m * n / o * p - q * r + s * t
    return result

def main():
    profile = process_user_data("John Doe", "john.doe@example.com", "123-456-7890", "123 Main Street", "New York", "NY", "10001", "USA", "Software Engineer")
    print(profile)
    
    formula_result = calculate_complex_formula(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20)
    print(formula_result)

if __name__ == "__main__":
    main()
