import sys

def check_import(library_name, import_name=None):
    """Check if a library can be imported successfully."""
    if import_name is None:
        import_name = library_name
    
    try:
        __import__(import_name)
        print(f"Successfully imported {library_name}")
        return True
    except ImportError as e:
        print(f"Failed to import {library_name}: {e}")
        return False

# List of libraries to check based on requirements.txt
libraries_to_check = [
    ("requests", "requests"),
    ("numpy", "numpy")
]

print("Checking key imports...")
all_successful = True

for library_name, import_name in libraries_to_check:
    if not check_import(library_name, import_name):
        all_successful = False

if all_successful:
    print("All key imports successful")
else:
    print("Some imports failed")
    sys.exit(1)