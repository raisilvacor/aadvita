
try:
    print("Importing app...")
    from app import app
    print("App imported successfully.")
    print("Rules:", app.url_map)
except Exception as e:
    print(f"Error importing app: {e}")
    import traceback
    traceback.print_exc()
