def calc(x, y):
    return x + y

def ProcessData(data):
    result = []
    for i in data:
        result.append(i * 2)
    return result

class myClass:
    def __init__(self):
        self.value = 0
    
    def get_value(self):
        return self.value

def main():
    a = 5
    b = 10
    c = calc(a, b)
    print(c)
    
    data = [1, 2, 3]
    processed = ProcessData(data)
    print(processed)
    
    obj = myClass()
    print(obj.get_value())

if __name__ == "__main__":
    main()
