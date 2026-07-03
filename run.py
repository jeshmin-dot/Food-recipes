import importlib.util
from pathlib import Path


module_path = Path(__file__).with_name("app.py")
spec = importlib.util.spec_from_file_location("recipe_site_app", module_path)
recipe_site_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe_site_app)
app = recipe_site_app.app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
