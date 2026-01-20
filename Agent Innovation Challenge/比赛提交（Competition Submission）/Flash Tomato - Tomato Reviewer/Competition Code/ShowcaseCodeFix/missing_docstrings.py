class Calculator:
    def __init__(self):
        self.result = 0
    
    def add(self, x, y):
        return x + y
    
    def subtract(self, x, y):
        return x - y
    
    def multiply(self, x, y):
        return x * y

def process_items(items):
    result = []
    for item in items:
        if item > 0:
            result.append(item * 2)
    return result

def calculate_average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)

def main():
    calc = Calculator()
    print(calc.add(5, 3))
    
    items = [1, 2, 3, 4, 5]
    processed = process_items(items)
    print(processed)
    
    avg = calculate_average([10, 20, 30])
    print(avg)

if __name__ == "__main__":
    main()
