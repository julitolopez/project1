import os
import requests

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():
    session["user_id"] = None
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/success", methods=["POST"])
def success():
    name = request.form.get("name")
    password = request.form.get("password")
    if db.execute("SELECT * FROM users_table WHERE name = :name", {"name": name}).rowcount == 1:
        return render_template("sorry.html")
    else:
        db.execute("INSERT INTO users_table (name, password) VALUES (:name, :password)",
        {"name": name, "password": password})
    db.commit()
    return render_template("success.html")

@app.route("/logout")
def logout():
    if session["user_id"] == 0:
        return render_template("sorry.html")
    else:
        session["user_id"] = 0
        return render_template("logout.html")

@app.route("/access", methods=["POST"])
def access():
    name = request.form.get("name")
    password = request.form.get("password")
    if db.execute("SELECT * FROM users_table WHERE name = :name AND password = :password",
        {"name": name, "password": password}).rowcount == 1:
        user = db.execute("SELECT * FROM users_table WHERE name = :name AND password = :password",
            {"name": name, "password": password}).fetchone()
        session["user_id"] = user[0]
        session["name"] = user[1]
        return render_template("access.html", user=user)
    else:
        return render_template("sorry.html")

@app.route("/sorry")
def sorry():
    return render_template("sorry.html")

@app.route("/search")
def search():
    if session["user_id"] == None:
        return render_template("sorry.html")
    else:
        return render_template("search.html")

@app.route("/results", methods=['POST'])
def results():
    title = request.form.get("title")
    author = request.form.get("author")
    isbn = request.form.get("isbn")
    books = db.execute(f"SELECT * FROM books_table WHERE title LIKE '%{title}%' AND author LIKE '%{author}%' AND isbn LIKE '%{isbn}%' ORDER BY title").fetchall()
    count = db.execute(f"SELECT * FROM books_table WHERE title LIKE '%{title}%' AND author LIKE '%{author}%' AND isbn LIKE '%{isbn}%'").rowcount
    return render_template("results.html", books=books, count=count)

@app.route("/book_page/<string:isbn>")
def book_page(isbn):
    if session["user_id"] == None:
        return render_template("login.html")
    book = db.execute("SELECT * FROM books_table WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    reviews = db.execute("SELECT reviews_table.id AS review_id, books_table_id, users_table_id, review, score, name, users_table.id FROM reviews_table JOIN users_table ON users_table.id = reviews_table.users_table_id WHERE books_table_id = :id", {"id": book.id}).fetchall()
    accept_review = db.execute("SELECT users_table_id FROM reviews_table WHERE books_table_id = :book_id AND users_table_id = :user_id", {"book_id": book.id, "user_id": session["user_id"]}).fetchone()
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "xEqv73cyTzqt1RuJ3agtQ", "isbns": isbn})
    data = res.json()
    books = data["books"]
    metrics = books[0]
    average_rating = metrics["average_rating"]
    work_ratings_count = metrics["work_ratings_count"]
    return render_template("book_page.html", book=book, reviews=reviews, accept_review=accept_review, average_rating=average_rating, work_ratings_count=work_ratings_count)

@app.route("/add_review/<string:isbn>", methods=['POST'])
def add_review(isbn):
    if session["user_id"] == None:
        return render_template("login.html")
    review = request.form.get("review")
    score = request.form.get("score")
    book_id = db.execute("SELECT * FROM books_table WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    db.execute("INSERT INTO reviews_table (books_table_id, users_table_id, review, score) VALUES (:books_table_id, :users_table_id, :review, :score)", {"books_table_id": book_id.id, "users_table_id": session["user_id"], "review": review, "score": score})
    db.commit()
    return redirect (url_for('book_page', isbn=isbn))

@app.route("/delete_review/<string:isbn>/<int:review_id>")
def delete_review(isbn, review_id):
    if session["user_id"] == None:
        return render_template("login.html")
    db.execute("DELETE FROM reviews_table WHERE id = :id", {"id": review_id})
    db.commit()
    return redirect (url_for('book_page', isbn=isbn))

@app.route("/api/<string:isbn>")
def api(isbn):
    api_response = db.execute("SELECT title, author, year, isbn, COUNT(users_table_id), CAST(ROUND(AVG(score), 2) AS FLOAT) FROM reviews_table RIGHT JOIN books_table ON books_table.id = reviews_table.books_table_id WHERE isbn = :isbn GROUP BY title, author, year, isbn", {"isbn": isbn}).fetchone()
    isbn_response = db.execute("SELECT * FROM books_table WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if isbn_response == None:
        return jsonify({"error": "No reviews for this book"}), 404
    return jsonify({
        "title": api_response.title,
        "author": api_response.author,
        "year": api_response.year,
        "review_count": api_response.count,
        "average_score": api_response.round
        })
