import os
import sys
import json
import re

def badFunctionName(x, y, z, a, b, c, d, e, f, g, h, i, j):
    unused_var = 100
    temp1 = x + y
    temp2 = z * a
    temp3 = b - c
    temp4 = d / e
    temp5 = f + g
    temp6 = h * i
    temp7 = j - temp1
    temp8 = temp2 + temp3
    temp9 = temp4 * temp5
    temp10 = temp6 / temp7
    temp11 = temp8 + temp9
    temp12 = temp10 - temp11
    result = temp12 * 2
    return result

class badClassName:
    def __init__(self):
        self.value = 0
    
    def method1(self, param1, param2, param3, param4, param5, param6, param7, param8):
        unused_local = 50
        return param1 + param2

def ProcessData(data):
    if data:
        processed = data * 2
        return processed

def main():
    result = badFunctionName(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
    print(result)
    
    obj = badClassName()
    print(obj.method1(1, 2, 3, 4, 5, 6, 7, 8))
    
    processed = ProcessData(10)
    print(processed)

if __name__ == "__main__":
    main()
