from flask import Flask, render_template

from recipes import RECIPES

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html", recipes=RECIPES)

if __name__ == "__main__":
    app.run(debug=True)
