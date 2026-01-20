def solve_polynomial_equation(a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z):
    discriminant = (b**2 - 4*a*c) * (e**2 - 4*d*f) * (h**2 - 4*g*i)
    numerator = (j*k + l*m - n*o) * (p*q - r*s) + (t*u + v*w) * (x*y - z*a)
    denominator = (b*c + d*e) * (f*g + h*i) - (j*k + l*m) * (n*o + p*q)
    result = (discriminant * numerator) / denominator if denominator != 0 else 0
    return result

def calculate_multivariate_statistics(x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15, x16, x17, x18, x19, x20, x21, x22, x23, x24, x25, x26):
    mean = (x1 + x2 + x3 + x4 + x5 + x6 + x7 + x8 + x9 + x10 + x11 + x12 + x13 + x14 + x15 + x16 + x17 + x18 + x19 + x20 + x21 + x22 + x23 + x24 + x25 + x26) / 26
    variance = ((x1-mean)**2 + (x2-mean)**2 + (x3-mean)**2 + (x4-mean)**2 + (x5-mean)**2 + (x6-mean)**2 + (x7-mean)**2 + (x8-mean)**2 + (x9-mean)**2 + (x10-mean)**2 + (x11-mean)**2 + (x12-mean)**2 + (x13-mean)**2 + (x14-mean)**2 + (x15-mean)**2 + (x16-mean)**2 + (x17-mean)**2 + (x18-mean)**2 + (x19-mean)**2 + (x20-mean)**2 + (x21-mean)**2 + (x22-mean)**2 + (x23-mean)**2 + (x24-mean)**2 + (x25-mean)**2 + (x26-mean)**2) / 26
    return mean, variance

def solve_linear_system(a11, a12, a13, a14, a15, a21, a22, a23, a24, a25, a31, a32, a33, a34, a35, a41, a42, a43, a44, a45, a51, a52, a53, a54, a55, b1, b2, b3, b4, b5):
    det = (a11 * a22 * a33 * a44 * a55) - (a11 * a22 * a33 * a45 * a54) - (a11 * a22 * a34 * a43 * a55) + (a11 * a22 * a34 * a45 * a53) + (a11 * a22 * a35 * a43 * a54) - (a11 * a22 * a35 * a44 * a53)
    x1 = (b1 * a22 * a33 * a44 * a55) / det if det != 0 else 0
    x2 = (a11 * b2 * a33 * a44 * a55) / det if det != 0 else 0
    x3 = (a11 * a22 * b3 * a44 * a55) / det if det != 0 else 0
    x4 = (a11 * a22 * a33 * b4 * a55) / det if det != 0 else 0
    x5 = (a11 * a22 * a33 * a44 * b5) / det if det != 0 else 0
    return [x1, x2, x3, x4, x5]

def compute_neural_network_layer(input1, input2, input3, input4, input5, input6, input7, input8, weight1, weight2, weight3, weight4, weight5, weight6, weight7, weight8, bias1, bias2, bias3, bias4, bias5, bias6, bias7, bias8, activation_param1, activation_param2):
    output1 = (input1 * weight1 + input2 * weight2 + input3 * weight3 + input4 * weight4 + bias1) * activation_param1
    output2 = (input5 * weight5 + input6 * weight6 + input7 * weight7 + input8 * weight8 + bias2) * activation_param2
    output3 = (input1 * weight2 + input3 * weight4 + input5 * weight6 + input7 * weight8 + bias3) * activation_param1
    output4 = (input2 * weight1 + input4 * weight3 + input6 * weight5 + input8 * weight7 + bias4) * activation_param2
    return [output1, output2, output3, output4]

def main():
    result1 = solve_polynomial_equation(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26)
    print(f"Polynomial result: {result1}")
    
    stats = calculate_multivariate_statistics(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26)
    print(f"Mean: {stats[0]}, Variance: {stats[1]}")
    
    solution = solve_linear_system(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 1, 2, 3, 4, 5)
    print(f"Solution: {solution}")

if __name__ == "__main__":
    main()
