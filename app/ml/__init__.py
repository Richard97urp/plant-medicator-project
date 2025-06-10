def __init__(self, db_params):
    self.db_params = db_params
    try:
        test_data = self.get_data_from_db()
        print(f"Loaded {len(test_data)} training records")
        print("Available columns:", test_data.columns.tolist())
        print("\nSample data types:")
        print(test_data.dtypes)
    except Exception as e:
        print(f"Error loading training data: {str(e)}")