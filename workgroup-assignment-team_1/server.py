from flask import Flask, render_template, request, session, redirect, url_for
from sqlalchemy import create_engine
from werkzeug.security import generate_password_hash, check_password_hash
import time

tweeter = Flask(__name__)
tweeter.config["SECRET_KEY"] = "this is not secret, remember, change it!"
engine = create_engine("sqlite:///tweeter.db")


@tweeter.route("/")
def index():
    tweets = []
    liked_tweets = []
    if "username" in session:
        query = f"""
        SELECT u.id, u.picture, u.username, t.tweet, t.id
        FROM tweets t
        INNER JOIN users u ON t.user_id=u.id
        INNER JOIN follows f ON f.followee_id=u.id
        WHERE f.follower_id={session['user_id']} OR u.id={session['user_id']}
        """

        likes_query = f"""
            SELECT tweet_id
            FROM likes
            WHERE user_id={session['user_id']}
            """

        with engine.connect() as connection:
            tweets = connection.execute(query).fetchall()
            liked_tweets = [x[0] for x in connection.execute(likes_query).fetchall()]

    return render_template("index.html", tweets=tweets, liked_tweets=liked_tweets)


@tweeter.route("/register")
def register():
    return render_template("register.html")


@tweeter.route("/register", methods=["POST"])
def handle_register():
    username = request.form["username"]
    password = request.form["password"]
    picture = request.form["picture"]

    hashed_password = generate_password_hash(password)

    insert_query = f"""
    INSERT INTO users(username, picture, password)
    VALUES ('{username}', '{picture}', '{hashed_password}')
    """

    with engine.connect() as connection:
        connection.execute(insert_query)

        return redirect(url_for("index"))


@tweeter.route("/users")
def users():
    if "user_id" not in session:
        return render_template("403.html"), 403

    users_query = """
    SELECT id, username, picture
    FROM users
    """

    followers_query = f"""
        SELECT follower_id, followee_id
        FROM follows
        WHERE follower_id={session['user_id']}
    """

    with engine.connect() as connection:
        users = connection.execute(users_query)
        follows = connection.execute(followers_query).fetchall()
        followee_ids = [y for x in follows for y in x]
        return render_template("users.html", users=users, current_user=session['user_id'], followee_ids=followee_ids)


@tweeter.route("/users/<user_id>")
def user_detail(user_id):
    user_query = f"""
    SELECT id, username, picture
    FROM users
    where id={user_id}
    """

    tweets_query = f"""
    SELECT tweet, id
    FROM tweets
    WHERE user_id={user_id}
    """

    likes_query = f"""
    SELECT tweet_id
    FROM likes
    WHERE user_id={session['user_id']}
    """

    with engine.connect() as connection:
        user = connection.execute(user_query).fetchone()
        tweets = connection.execute(tweets_query).fetchall()
        liked_tweets = [x[0] for x in connection.execute(likes_query).fetchall()]

        if user:
            return render_template("user_detail.html", user=user, tweets=tweets, liked_tweets=liked_tweets)
        else:
            return render_template("404.html"), 404


@tweeter.route("/login")
def login():
    return render_template("login.html")


@tweeter.route("/login", methods=["POST"])
def handle_login():
    username = request.form["username"]
    password = request.form["password"]

    login_query = f"""
    SELECT password, id
    FROM users
    WHERE username='{username}'
    """

    with engine.connect() as connection:
        user = connection.execute(login_query).fetchone()

        if user and check_password_hash(user[0], password):
            session["user_id"] = user[1]
            session["username"] = username
            return redirect(url_for("index"))
        else:
            return render_template("404.html"), 404


@tweeter.route("/logout")
def logout():
    session.pop("username")
    session.pop("user_id")

    return redirect(url_for("index"))


@tweeter.route("/tweet", methods=["POST"])
def handle_tweet():
    tweet = request.form["tweet"]

    insert_query = f"""
    INSERT INTO tweets(tweet, user_id)
    VALUES ('{tweet}', {session['user_id']})
    """

    with engine.connect() as connection:
        connection.execute(insert_query)

        return redirect(url_for("index"))


@tweeter.route("/follow/<followee>")
def follow(followee):
    if "user_id" not in session:
        return render_template("403.html"), 403

    follower = session["user_id"]

    insert_query = f"""
    INSERT INTO follows(follower_id, followee_id)
    VALUES ({follower}, {followee})
    """

    with engine.connect() as connection:
        connection.execute(insert_query)

        return redirect(url_for("users"))


@tweeter.route("/unfollow/<followee>")
def unfollow(followee):
    if "user_id" not in session:
        return render_template("403.html"), 403

    delete_query = f"""
    DELETE FROM follows
    WHERE follower_id={session["user_id"]} AND followee_id={followee}
    """

    with engine.connect() as connection:
        connection.execute(delete_query)

        return redirect(url_for("users"))


@tweeter.route("/message/<recipient_id>")
def message(recipient_id):
    sender_query = f"""
    SELECT id, username, picture
    FROM users
    where id={session['user_id']}
    """

    recipient_query = f"""
    SELECT id, username, picture
    FROM users
    where id={recipient_id}
    """

    messages_query = f"""
    SELECT text, from_id, time
    FROM messages
    WHERE (from_id={session['user_id']} AND to_id={recipient_id}) 
    OR (to_id={session['user_id']} AND from_id={recipient_id})
    """

    with engine.connect() as connection:
        sender = connection.execute(sender_query).fetchone()
        recipient = connection.execute(recipient_query).fetchone()
        messages = connection.execute(messages_query).fetchall()[::-1]

        if recipient:
            return render_template("send_message.html", sender=sender, recipient=recipient, messages=messages)
        else:
            return render_template("404.html"), 404


@tweeter.route('/send-message/<recipient_id>', methods=['GET', 'POST'])
def handle_message(recipient_id):
    if "user_id" not in session:
        return render_template("403.html"), 403

    sender_id = session["user_id"]
    message_body = request.form["message-body"]
    t = time.localtime()
    current_time = time.strftime("%H:%M:%S", t)

    insert_query = f"""
            INSERT INTO messages(text, from_id, to_id, time)
            VALUES ('{message_body}', '{sender_id}', '{recipient_id}', '{current_time}')
            """

    with engine.connect() as connection:
        connection.execute(insert_query)

        return redirect(url_for("message", recipient_id=recipient_id))


@tweeter.route('/search', methods=['POST'])
def search():
    if "user_id" not in session:
        return render_template("403.html"), 403

    searched = request.form["searched"]

    search_query = f"""
    SELECT u.id, u.picture, u.username, t.tweet
    FROM tweets t
    INNER JOIN users u ON t.user_id=u.id
    INNER JOIN follows f ON f.followee_id=u.id
    WHERE f.follower_id={session['user_id']} AND (t.tweet LIKE '%{searched}%')
    """

    with engine.connect() as connection:
        tweets = connection.execute(search_query).fetchall()

    return render_template("search.html", searched=searched, tweets=tweets)


@tweeter.route('/like/<tweet_id>/<user_id>')
def like(tweet_id, user_id):
    if "user_id" not in session:
        return render_template("403.html"), 403

    insert_query = f"""
    INSERT INTO likes(user_id, tweet_id)
    VALUES ({session['user_id']}, {tweet_id})
    """

    with engine.connect() as connection:
        connection.execute(insert_query)

        return redirect(url_for("user_detail", user_id=user_id))


@tweeter.route('/dislike/<tweet_id>/<user_id>')
def dislike(tweet_id, user_id):
    if "user_id" not in session:
        return render_template("403.html"), 403

    delete_query = f"""
    DELETE FROM likes
    WHERE user_id={session["user_id"]} AND tweet_id={tweet_id}
    """

    with engine.connect() as connection:
        connection.execute(delete_query)

        return redirect(url_for("user_detail", user_id=user_id))


tweeter.run(debug=True)
