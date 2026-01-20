def process_data(data):
    unused_var = 100
    temp_result = data * 2
    intermediate_value = temp_result + 10
    final_result = intermediate_value - 5
    return final_result

def calculate_stats(numbers):
    count = len(numbers)
    total = sum(numbers)
    average = total / count
    unused_count = count * 2
    variance = sum((x - average) ** 2 for x in numbers) / count
    return average, variance

def main():
    data = 5
    result = process_data(data)
    print(result)
    
    numbers = [1, 2, 3, 4, 5]
    avg, var = calculate_stats(numbers)
    print(f"Average: {avg}, Variance: {var}")

if __name__ == "__main__":
    main()
