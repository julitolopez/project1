import requests

isbn = '0380795272'

res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "xEqv73cyTzqt1RuJ3agtQ", "isbns": isbn})
data = res.json()
books = data["books"]
metrics = books[0]
average_rating = metrics["average_rating"]
work_ratings_count = metrics["work_ratings_count"]

print(average_rating)
print(work_ratings_count)
