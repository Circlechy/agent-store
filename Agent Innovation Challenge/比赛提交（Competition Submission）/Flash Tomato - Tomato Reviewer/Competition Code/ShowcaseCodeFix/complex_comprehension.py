def process_matrix(matrix):
    result = [[sum([x * y for y in row if y > 0]) for x in row if x % 2 == 0] for row in matrix if len(row) > 0]
    return result

def filter_and_transform(data):
    output = {k: [v * 2 for v in values if v > 0] for k, values in data.items() if len(values) > 0 for value in values if value % 2 == 0}
    return output

def nested_comprehension(items):
    result = [[[i * j * k for k in range(1, 6) if k % 2 == 0] for j in range(1, 5) if j > 2] for i in items if i > 0]
    return result

def complex_dict_comprehension(users, permissions, roles):
    user_permissions = {user: {perm: [role for role in roles if role in user_roles and perm in role_perms] for perm in permissions if perm in user_perms} for user, user_roles in users.items() for user_perms in [permissions.get(user, [])] if user_roles}
    return user_permissions

def main():
    matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    processed = process_matrix(matrix)
    print(processed)
    
    data = {"a": [1, 2, 3], "b": [4, 5, 6]}
    filtered = filter_and_transform(data)
    print(filtered)
    
    items = [1, 2, 3, 4, 5]
    nested = nested_comprehension(items)
    print(nested)

if __name__ == "__main__":
    main()
