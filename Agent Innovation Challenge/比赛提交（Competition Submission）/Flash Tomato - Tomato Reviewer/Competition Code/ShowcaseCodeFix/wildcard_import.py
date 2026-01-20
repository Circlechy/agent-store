from math import *
from os import *
from sys import *
from typing import *

def calculate_circle_area(radius):
    return pi * radius ** 2

def get_environment_variable(name):
    return environ.get(name)

def exit_program(code):
    exit(code)

def process_data(data):
    result = List[int]()
    for item in data:
        result.append(item * 2)
    return result

def main():
    area = calculate_circle_area(5)
    print(f"Area: {area}")
    
    env_var = get_environment_variable("PATH")
    print(f"PATH: {env_var}")

if __name__ == "__main__":
    main()
