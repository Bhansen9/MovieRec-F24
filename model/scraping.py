## Scraping for Letterboxd using BeautifulSoup and requests

# imports used
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json


def scrape_letterboxd(username: str):
    page_number = 1
    movie_names = []
    movie_slugs = []
    movie_ratings = []
    movie_images = []
    while True:
        # Given the username, create the letterboxd url so we can scrape the movies
        url = "https://letterboxd.com/" + username.strip() + "/films/page/" + str(page_number) + "/"
        response = requests.get(url)

        # Initialize the regular expressions which will scan the soup file
        # for all of the movie names and star ratings.
        regex_movie_names = re.compile(r'alt="([^"]+)"')
        regex_movie_slugs = re.compile(r'data-film-slug="([^"]+)"')
        regex_movie_ratings = re.compile(r"rated-(\d+)")

        # Make the soup to pull everything off the users letterboxd webpage.
        soup = BeautifulSoup(requests.get(url).text, "html.parser")

        # Now find everything from only the actual movie section of the webpage, not the other info
        film_html = soup.find_all("li", class_=re.compile(r"poster-container"))

        # If there aren't any films found, break out of the loop
        if not film_html:
            break

        # Now, using regex, we get all the movie names and ratings from the HTML file.
        # This automatically creates a list for each variable.
        movie_names = re.findall(regex_movie_names, str(film_html))
        movie_slugs = re.findall(regex_movie_slugs, str(film_html))
        movie_ratings = re.findall(regex_movie_ratings, str(film_html))

        page_number += 1

    """ Now we're going to remove the movies from the users letterbox'd that don't
        have a rating associated with them. Because it won't add to the model and
        it will break when we try and create a dataframe.   """
    # We now get the url for the movies that don't have any reviews.
    url_no_reviews = "https://letterboxd.com/" + username.strip() + "/films/rated/none/"

    # Make the soup to pull everything off that webpage.
    soup = BeautifulSoup(requests.get(url_no_reviews).text, "html.parser")

    # Now scrape everything from only the reviews section. that is the 'list__...'
    film_html_no_reviews = soup.find_all("li", class_=re.compile(r"poster-container"))

    # Get the list of all the removed movies.
    removed_movie_names = re.findall(r'alt="([^"]+)"', str(film_html_no_reviews))
    removed_movie_slugs = re.findall(r'data-film-slug="([^"]+)"', str(film_html_no_reviews))

    """ Loop over all the movies we found, and remove them so that
    len(movie_names) == len(movie_ratings) and we don't have movies without ratings
    If the movie exists within the lists we should remove it
    We wont need this when we scrape all the movies instead of
    only the first page. """
    movie_names = [movie for movie in movie_names if movie not in removed_movie_names]
    movie_slugs = [movie for movie in movie_slugs if movie not in removed_movie_slugs]
    movie_ratings = [int(rating) for rating in movie_ratings]

    # Get the images for the movies
    # Lowkey stole this code from https://stackoverflow.com/questions/73803684/trying-to-scrape-posters-from-letterboxd-python
    movie_images = []
    for movie in movie_slugs:
        url = f"https://letterboxd.com/film/{movie}/"
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")

        script_w_data = soup.select_one('script[type="application/ld+json"]')
        json_obj = json.loads(script_w_data.text.split(" */")[1].split("/* ]]>")[0])
        movie_images.append(json_obj["image"])

    # Return the results
    return movie_names, movie_slugs, movie_ratings, movie_images


def scrape_letterboxd_movie(movie_slug: str):
    """
    Scrapes details of a specific movie from Letterboxd using its slug.

    Args:
    - movie_slug: The slug part of the movie URL on Letterboxd (e.g., 'joker-folie-a-deux' for 'letterboxd.com/film/joker-folie-a-deux/')

    Returns:
    - Dictionary containing movie title, release year, genres, director, rating, actors (with Wikipedia URLs), poster image URL, summary, and reviews.
    """
    url = f"https://letterboxd.com/film/{movie_slug}/"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(f"Failed to retrieve data. Status code: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract JSON-LD data which contains movie details
    script_data = soup.select_one('script[type="application/ld+json"]')
    if not script_data:
        raise ValueError("Movie data not found on the page.")

    # Get the content of the script and strip the CDATA tags
    raw_data = script_data.string
    cleaned_data = re.sub(r"/\* <!\[CDATA\[ \*/|/\* \]\]> \*/", "", raw_data).strip()

    # Parse JSON data
    try:
        movie_data = json.loads(cleaned_data)
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", str(e))
        return None

    # Extract details from the JSON data
    title = movie_data.get("name", "Unknown Movie")
    year_element = soup.find("a", href=re.compile(r"/films/year/\d{4}/"))
    year = year_element.text if year_element else "N/A"

    genres = movie_data.get("genre", [])
    director = movie_data.get("director", [{}])[0].get("name", "N/A")
    rating = movie_data.get("aggregateRating", {}).get("ratingValue", 0.0)
    poster_url = movie_data.get("image", "https://via.placeholder.com/150")

    # Extract actors and create Wikipedia links for each
    actors = [
        {
            "name": actor["name"],
            "wiki_url": f"https://en.wikipedia.org/wiki/{actor['name'].replace(' ', '_')}",
        }
        for actor in movie_data.get("actors", [])
    ]

    # Extract the summary
    summary_tag = soup.find("meta", property="og:description")
    summary = summary_tag["content"] if summary_tag else "No summary available"

    reviews = []
    review_elements = soup.find_all("li", class_="film-detail")

    for review in review_elements:
        reviewer_name = (
            review.find("strong", class_="name").text.strip()
            if review.find("strong", class_="name")
            else "Unknown"
        )

        # Check for hidden-spoiler text first, then fallback to main body-text div
        review_content_div = review.find(
            "div", class_="hidden-spoilers expanded-text"
        ) or review.find("div", class_="body-text -prose collapsible-text")

        # Get all paragraphs within the selected review content and join them
        if review_content_div:
            paragraphs = review_content_div.find_all("p")
            review_content = " ".join(p.text.strip() for p in paragraphs)
        else:
            review_content = "No content available"

        like_count = (
            review.find("p", class_="like-link-target").get("data-count", "0")
            if review.find("p", class_="like-link-target")
            else "0"
        )

        # Append each review to the list
        reviews.append({"reviewer": reviewer_name, "content": review_content, "likes": like_count})

    # Return the results in a dictionary
    return {
        "title": title,
        "year": year,
        "genres": genres,
        "director": director,
        "rating": rating,
        "actors": actors,
        "movie_image": poster_url,
        "summary": summary,
        "reviews": reviews,
    }


def scrape_recommended_movies(movie_slugs):
    movie_data = []  # List to hold data for each recommended movie

    for movie_slug in movie_slugs:
        # Construct the URL for each recommended movie
        url = f"https://letterboxd.com/film/{movie_slug}/"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract the JSON-LD data for each movie
        script_with_data = soup.select_one('script[type="application/ld+json"]')

        if script_with_data:  # Ensure that script_with_data is not None
            try:
                json_obj = json.loads(script_with_data.text.split(" */")[1].split("/* ]]>")[0])

                # Extract movie title, ID (slug), and image URL
                movie_title = json_obj["name"]
                movie_image = json_obj["image"]
                movie_id = movie_slug
                try:
                    movie_rating = json_obj["aggregateRating"]["ratingValue"]
                except KeyError:
                    movie_rating = ""

                # Append data to list as a dictionary
                movie_data.append(
                    {"title": movie_title, "movie_id": movie_id, "image": movie_image, "rating": movie_rating}
                )
            except Exception as e:
                print(f"Error parsing JSON-LD for {movie_slug}: {e}")
        else:
            print(f"Warning: No JSON-LD data found for {movie_slug}")

    return movie_data


# Method to scrape a given letterboxd username and return a dataframe with the movie names and the star ratings.
def scrape_and_make_dataframe(username: str) -> pd.DataFrame:
    # Scrape the movies and ratings from the given letterboxd username
    (movie_name, movie_slugs, movie_rating, movie_images) = scrape_letterboxd(username)

    # Convert the ratings from string to integer using list comprehension
    int_movie_ratings = [int(i) for i in movie_rating]

    # Make a list of size (movie_name) for the usernames, Not necessary just included it
    username_list = [username] * len(movie_name)

    # Return the results as a Pandas dataframe
    return pd.DataFrame(
        {
            "user_name": username_list,
            "film_id": movie_slugs,
            "Movie_name": movie_name,
            "rating": int_movie_ratings,
            "image": movie_images,
        }
    )


if __name__ == "__main__":
    # Sample use
    username = input("Please type your letterboxd username : ")
    print(f"Now scraping : {username}")
    df = scrape_and_make_dataframe(username.strip())
    print(df)
