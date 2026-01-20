def process_data(data):
    if data:
        processed = data * 2
        return processed
    else:
        return undefined_result

def calculate_total(items):
    total = 0
    for item in items:
        total += item.price
    return total + missing_value

def main():
    numbers = [1, 2, 3, 4, 5]
    result = process_data(numbers)
    print(result)

if __name__ == "__main__":
    main()
