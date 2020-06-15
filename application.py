import os
import requests

from flask import Flask, session, render_template, url_for, request, jsonify
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
@app.route("/login", methods=["POST", "GET"])
def login():
    if session.get('username'):
        return render_template('success.html')

    # Get information from the user
    username = str(request.form.get("username")).capitalize()
    password = str(request.form.get('password'))

    # process the information
    if request.method == "POST":
        username_input = db.execute(
            "SELECT * FROM users WHERE username = :username", {"username": username}).rowcount > 0
        userpassword_input = db.execute(
            "SELECT * FROM users WHERE password = :password", {"password": password}).rowcount > 0
        if username_input and userpassword_input:
            session["username"] = username
            print(session["username"])
            return render_template("success.html")

    return render_template("login.html")


@app.route("/sign", methods=["POST", "GET"])
def sign():
    if request.method == "POST":
        # Get informations from the form
        username = str(request.form.get("username")).capitalize()
        password = str(request.form.get("password"))
        password1 = str(request.form.get("password1"))

        # check that password match
        if password != password1:
            return render_template("sign.html")

        # check that username doesn't exit before and then add to the database
        if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).rowcount > 0:
            return render_template("sign.html", message=True)
        else:
            db.execute("INSERT INTO users (username,password) VALUES (:username, :password)", {
                       "username": username, "password": password})
        db.commit()
        return render_template("login.html")

    return render_template("sign.html")


@app.route("/logout")
def logout():
    session.pop('username', None)
    return render_template("login.html")


@app.route("/success", methods=['POST', 'GET'])
def success():
    if request.method == 'POST':
        # GET search input
        get_search = str(request.form.get('search'))
        search = "%{}%".format(get_search)
        # search the database and produce output
        results = db.execute(
            "SELECT * FROM books WHERE author LIKE :search OR title  LIKE :search OR isbn LIKE :search ", {"search": search})
        count = results.rowcount
        return render_template('success.html', results=results, count=count)

    return render_template('success.html')


@app.route("/book/<isbn>", methods=["POST", "GET"])
def book(isbn):
   
    search = "%{}%".format(isbn)
    results = db.execute(
        "SELECT * FROM books WHERE author LIKE :search OR title  LIKE :search OR isbn LIKE :search ", {"search": search})
    # form review
    ratings = request.form.get('rating')
    comments = str(request.form.get('comments'))
    #be sure user is logged in
    try:
        username = session['username']
    except KeyError :
        return render_template('login.html')
    #processing form data
    if request.method == "POST":
        # check if username already exist in review table
        if db.execute("SELECT * FROM reviews WHERE username = :username", {"username": username}).rowcount > 0 and db.execute("SELECT * FROM reviews WHERE book = :isbn", {"isbn": isbn}).rowcount > 0:
            return render_template("book.html", isbn=isbn, results=results, message=True)
        # add review to the table
        db.execute(
            "INSERT INTO reviews (username,book,comments,ratings) VALUES (:username, :book, :comments, :ratings)", {
                "username": username, "book": isbn, "comments": comments, "ratings": ratings})
        db.commit()
    #Get data from goodreads Api
    goodreads = requests.get("https://www.goodreads.com/book/review_counts.json",
                             params={"key": "7qUMh7xsPND3ETGgihszsA", "isbns": isbn})
    book = goodreads.json()
    bookRate = book['books'][0]['ratings_count']
    average = book['books'][0]['average_rating']

    return render_template('book.html', isbn=isbn, results=results, bookRate=bookRate, average=average)


@app.route('/api/<isbn>')
def api(isbn):
    #join the reviews and the books table
    books = db.execute("SELECT title, author, year, isbn, \
                    COUNT(reviews.id) as review_count, \
                    ROUND(AVG(reviews.ratings),1) as average_score \
                    FROM books \
                    INNER JOIN reviews \
                    ON books.isbn = reviews.book \
                    WHERE isbn = :isbn \
                    GROUP BY title, author, year, isbn",
                    {"isbn": isbn})
    #if the requested isbn isnt in my books table
    if books.rowcount < 1:
        return jsonify({"error": "Invalid isbn"}), 422
    #make data iterable
    books = books.fetchone()
    #convert average_score to a float
    score = float(books.average_score)
    #return a Json object
    return jsonify({
        "title": books.title,
        "author": books.author,
        "year": int(books.year),
        "isbn": books.isbn,
        "review_count": books.review_count,
        "average":score
    })
   
   # return render_template('api.html',book=book,average=average,review=review)
