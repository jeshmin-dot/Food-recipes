from flask import Flask, render_template

from recipes import RECIPES

app = Flask(__name__)

@app.route("/")
def home():
    categories = sorted({recipe["category"] for recipe in RECIPES})
    return render_template("index.html", recipes=RECIPES, categories=categories)

if __name__ == "__main__":
    app.run(debug=True)
