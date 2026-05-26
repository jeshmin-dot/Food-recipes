from flask import Flask, render_template

app = Flask(__name__)

recipes = [
    {
        "id": 1,
        "name": "Pizza",
        "ingredients": "Cheese, Dough, Tomato Sauce"
    },
    {
        "id": 2,
        "name": "Burger",
        "ingredients": "Bun, Patty, Cheese"
    }
]

@app.route("/")
def home():
    return render_template("index.html", recipes=recipes)

if __name__ == "__main__":
    app.run(debug=True)